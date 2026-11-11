"""HTTP client for the TMDB API: auth detection, pacing, retries, typed errors.

There is no gate to defeat here -- TMDB is a documented API that answers to a
key -- so this client is much plainer than the DataDome and Cloudflare clients
elsewhere in this portfolio. What it does have to get right is three things:

  * Accepting either credential form without being told which one it was given.
    TMDB issues a 32-character v3 API key and a long v4 JWT read-access token
    from the same settings page, and buyers paste whichever they copied first.
    A v3 key goes in the query string; a v4 token goes in an Authorization
    header. Sending one the other way is an instant 401, so the form is
    detected instead of configured.
  * Treating a bad key as fatal. A 401 will not come right on retry, and a run
    that retries it four times per request across 500 titles wastes the
    buyer's compute to arrive at the same answer. It stops the run at once.
  * Honouring Retry-After. TMDB's limiter is generous (~50 requests/second)
    but real, and it tells you exactly how long to wait when you cross it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    API_ROOT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    TLS_PROFILES,
    TMDB_INVALID_KEY,
    TMDB_RESOURCE_NOT_FOUND,
    TMDB_SUSPENDED_KEY,
)

log = logging.getLogger("tmdb.client")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)
DEFAULT_RATE_LIMIT_WAIT_SECS = 5.0


class TmdbError(Exception):
    """Base for the outcomes callers route on."""


class TmdbNotFound(TmdbError):
    """TMDB answered definitively that the resource does not exist.

    HTTP 404, or status_code 34 in the JSON body. Final answer: callers write a
    diagnostic row and move on rather than spending retries on it.
    """


class TmdbAuthError(TmdbError):
    """The key is missing, malformed, revoked or suspended.

    Fatal for the whole run. Never retried.
    """


class TmdbBlocked(TmdbError):
    """Transport failure, or a status that survived the whole retry ladder."""


class TmdbClient:
    """One client per run, holding a single curl_cffi session."""

    def __init__(
        self,
        api_key: str,
        *,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
        request_delay: float = DEFAULT_REQUEST_DELAY_SECS,
        language: str | None = None,
        region: str | None = None,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise TmdbAuthError(
                "No TMDB credential supplied. Put your API key in the "
                "'tmdbApiKey' input field. A free key takes about a minute: "
                "sign up at https://www.themoviedb.org/signup then open "
                "https://www.themoviedb.org/settings/api -- either the "
                "API Key or the API Read Access Token works here."
            )
        self.api_key = key
        # A v4 read-access token is a JWT: three dot-separated base64 segments
        # starting with the encoded header, which always renders as "eyJ".
        self.is_bearer = key.startswith("eyJ") and key.count(".") == 2
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self.language = language
        self.region = region

        self._profile_idx = 0
        self._session: cr.Session | None = None
        self._lock = asyncio.Lock()
        self._last_at = 0.0

        self.request_count = 0
        self.rate_limited_count = 0

    # -- session plumbing --------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.is_bearer:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _session_or_new(self) -> cr.Session:
        if self._session is None:
            kwargs: dict[str, Any] = {
                "impersonate": self.profile,
                "timeout": self.request_timeout,
                "headers": self._headers(),
            }
            if self.proxy_url:
                kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
            self._session = cr.Session(**kwargs)
        return self._session

    def rotate_profile(self) -> str:
        self._profile_idx += 1
        self.close()
        log.info("Rotated TLS profile to %s", self.profile)
        return self.profile

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
            self._session = None

    # -- pacing ------------------------------------------------------------

    async def _pace(self) -> None:
        if self.request_delay <= 0:
            return
        async with self._lock:
            gap = time.monotonic() - self._last_at
            if gap < self.request_delay:
                await asyncio.sleep(self.request_delay - gap)
            self._last_at = time.monotonic()

    # -- core --------------------------------------------------------------

    def build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Compose a full URL, applying run-wide defaults and the credential.

        `language` and `region` are applied here rather than at every call site
        so that one input field really does change every request in the run.
        A caller that passes its own value still wins.
        """
        url = path if path.startswith("http") else API_ROOT.rstrip("/") + "/" + path.lstrip("/")
        query: dict[str, Any] = {}
        if self.language:
            query["language"] = self.language
        if self.region:
            query["region"] = self.region
        for key, value in (params or {}).items():
            if value is None or value == "":
                continue
            query[key] = value
        if not self.is_bearer:
            query["api_key"] = self.api_key
        if query:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(query, doseq=True, safe=",|")
        return url

    def redact(self, url: str) -> str:
        """Strip the credential out of a URL before it is logged or published.

        Every record carries the exact endpoint it came from, which is only
        safe because the key never survives this function. A v4 token travels
        in a header and so never appears in a URL at all.
        """
        if not self.api_key or self.is_bearer:
            return url
        return url.replace(self.api_key, "REDACTED")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a TMDB endpoint and decode its JSON."""
        url = self.build_url(path, params)
        label = self.redact(url)
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            if attempt:
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info(
                    "Retry %d/%d for %s in %.1fs",
                    attempt, self.max_retries - 1, label, delay,
                )
                await asyncio.sleep(delay)

            await self._pace()
            session = self._session_or_new()
            self.request_count += 1
            try:
                resp = await asyncio.to_thread(session.get, url)
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", label, exc)
                self.rotate_profile()
                continue

            body = _json_body(resp)
            status = resp.status_code
            tmdb_status = body.get("status_code") if isinstance(body, dict) else None
            message = body.get("status_message") if isinstance(body, dict) else None

            if status == 401 or tmdb_status in (TMDB_INVALID_KEY, TMDB_SUSPENDED_KEY):
                raise TmdbAuthError(
                    f"TMDB rejected the credential ({message or 'HTTP 401'}). "
                    "Check it at https://www.themoviedb.org/settings/api -- "
                    "paste either the 32-character API Key or the long API "
                    "Read Access Token, with no surrounding quotes or spaces."
                )

            if status == 404 or tmdb_status == TMDB_RESOURCE_NOT_FOUND:
                raise TmdbNotFound(f"HTTP 404 on {label}")

            if status == 429:
                self.rate_limited_count += 1
                wait = _retry_after(resp, DEFAULT_RATE_LIMIT_WAIT_SECS)
                last_error = TmdbBlocked(f"HTTP 429 on {label}")
                log.warning(
                    "Rate limited by TMDB. Waiting %.0fs as instructed. Raise "
                    "requestDelaySecs if this repeats.", wait,
                )
                await asyncio.sleep(wait)
                continue

            if status in RETRY_STATUS:
                last_error = TmdbBlocked(f"HTTP {status} on {label}")
                log.warning("HTTP %s on %s", status, label)
                continue

            if status >= 400:
                raise TmdbBlocked(
                    f"HTTP {status} on {label}: {message or (resp.text or '')[:200]}"
                )

            if body is None:
                last_error = TmdbBlocked(
                    f"{label} answered HTTP {status} with a body that is not "
                    f"JSON ({len(resp.content)} bytes)"
                )
                log.warning("Non-JSON body on %s", label)
                continue

            return body

        raise TmdbBlocked(f"{label} failed after {self.max_retries} attempts") from last_error


def _json_body(resp: Any) -> Any:
    try:
        return json.loads(resp.text or "")
    except ValueError:
        return None


def _retry_after(resp: Any, fallback: float) -> float:
    raw = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
    try:
        # Cap it: a pathological header should not park the run for an hour.
        return max(1.0, min(float(raw), 120.0))
    except (TypeError, ValueError):
        return fallback
