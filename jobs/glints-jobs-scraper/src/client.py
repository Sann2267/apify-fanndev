"""HTTP client for Glints: TLS impersonation, backoff, profile rotation."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import random
import re
import uuid
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    BLOCK_MARKERS,
    GRAPHQL_URL,
    SEARCH_LOGIN_GATE,
    SITE_ROOT,
    TLS_PROFILES,
)

log = logging.getLogger("glints.client")


class GlintsBlocked(Exception):
    """The edge answered with a challenge instead of data."""


class GlintsLoginRequired(Exception):
    """Glints wants an account for this slice of the result set."""


class GlintsNotFound(Exception):
    """The id is well formed but Glints has no such job or company."""


class GlintsGraphQLError(Exception):
    """The API parsed the request and rejected it on its own terms."""


class GlintsClient:
    """One client per run, holding a curl_cffi session for the active profile.

    Glints does not gate on JA3 today, so the profile ladder exists only as a
    recovery path: a challenge body or an unexpected 403 rotates to the next
    profile and rebuilds the session, rather than failing the run outright.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        country_code: str = "ID",
        max_retries: int = 4,
        request_timeout: int = 45,
    ) -> None:
        self.proxy_url = proxy_url
        self.country_code = country_code
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self._profile_idx = 0
        self._session: cr.Session | None = None
        # Glints reads these off the browser for experiment bucketing. They are
        # not anti-bot tokens -- any well-formed UUID is accepted -- but sending
        # a stable pair per run keeps one run inside one experiment bucket
        # instead of straddling several.
        self._device_id = str(uuid.uuid4())
        self._session_id = str(uuid.uuid4())

    # -- session plumbing --------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    def _build_session(self) -> cr.Session:
        kwargs: dict[str, Any] = {
            "impersonate": self.profile,
            "timeout": self.request_timeout,
        }
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        return cr.Session(**kwargs)

    def _session_or_new(self) -> cr.Session:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    def rotate_profile(self) -> str:
        """Advance the ladder and drop the session so the next call re-handshakes."""
        self._profile_idx += 1
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must never mask the real error
                pass
        self._session = None
        log.warning("Rotated TLS profile to %s", self.profile)
        return self.profile

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    # -- headers -----------------------------------------------------------

    def _headers(self, referer: str) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "origin": SITE_ROOT,
            "referer": referer,
            "x-glints-country-code": self.country_code,
            "x-glints-device-id": self._device_id,
            "x-glints-tracking-session-id": self._session_id,
            "x-app-platform": "web",
            "apollographql-client-name": "glints-web",
        }

    # -- core call ---------------------------------------------------------

    @staticmethod
    def _looks_challenged(body: str) -> bool:
        low = body[:4000].lower()
        return any(m in low for m in BLOCK_MARKERS)

    async def graphql(
        self,
        operation: str,
        query: str,
        variables: dict[str, Any],
        referer: str | None = None,
    ) -> dict[str, Any]:
        """POST one operation, retrying with backoff and profile rotation.

        Returns the data object. Raises GlintsLoginRequired when Glints walls
        the slice behind an account, so callers can stop paging cleanly instead
        of treating it as a transport failure.
        """
        referer = referer or f"{SITE_ROOT}/{self.country_code.lower()}"
        payload = {
            "operationName": operation,
            "query": query,
            # The v2 resolver is Go, not Apollo Server, and rejects a missing or
            # null variables map with GRAPHQL_PARSE_FAILED. Always send a map.
            "variables": variables or {},
        }
        url = f"{GRAPHQL_URL}?op={operation}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if attempt:
                # Exponential backoff with jitter, capped so a long fan-out
                # cannot stall behind one bad slice.
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info(
                    "Retry %d/%d for %s in %.1fs",
                    attempt,
                    self.max_retries - 1,
                    operation,
                    delay,
                )
                await asyncio.sleep(delay)

            session = self._session_or_new()
            try:
                resp = await asyncio.to_thread(
                    session.post, url, json=payload, headers=self._headers(referer)
                )
            except Exception as exc:  # noqa: BLE001 - transport errors are all retryable
                last_error = exc
                log.warning("Transport error on %s: %s", operation, exc)
                self.rotate_profile()
                continue

            body = resp.text or ""

            if self._looks_challenged(body):
                last_error = GlintsBlocked(
                    f"challenge body on {operation} (HTTP {resp.status_code})"
                )
                self.rotate_profile()
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = GlintsGraphQLError(f"HTTP {resp.status_code} on {operation}")
                log.warning("HTTP %s on %s", resp.status_code, operation)
                continue

            try:
                parsed = json.loads(body)
            except ValueError:
                last_error = GlintsGraphQLError(
                    f"non-JSON body on {operation} (HTTP {resp.status_code}): {body[:200]}"
                )
                self.rotate_profile()
                continue

            errors = parsed.get("errors")
            if errors:
                message = "; ".join(str(e.get("message", e)) for e in errors)
                codes = {
                    (e.get("extensions") or {}).get("code")
                    for e in errors
                    if isinstance(e, dict)
                }
                if SEARCH_LOGIN_GATE in message.lower():
                    raise GlintsLoginRequired(message)
                if "RECORD_NOT_FOUND" in codes:
                    # A dead or delisted id. Retrying cannot resurrect it, and
                    # it is a fact about the entity rather than a failure, so
                    # callers turn this into a not_found row.
                    raise GlintsNotFound(message)
                if resp.status_code == 403:
                    # A 403 that is not the login wall is worth one rotation.
                    last_error = GlintsBlocked(f"403 on {operation}: {message}")
                    self.rotate_profile()
                    continue
                # A validation error will not heal on retry, so surface it now.
                raise GlintsGraphQLError(f"{operation}: {message}")

            data = parsed.get("data")
            if data is None:
                last_error = GlintsGraphQLError(
                    f"{operation}: null data, HTTP {resp.status_code}"
                )
                continue

            return data

        raise last_error or GlintsGraphQLError(
            f"{operation} failed after {self.max_retries} attempts"
        )

    # -- plain GET (sitemaps) ---------------------------------------------

    def _document_headers(self) -> dict[str, str]:
        """Headers for a plain GET of a sitemap or page.

        Cloudflare scores static paths differently from the JSON API: a
        header-less GET from a datacenter address is read as a bot and answered
        403, while the same address posting to /api/v2/graphql with a full
        header set is served normally. So document fetches carry the headers a
        browser would send rather than relying on impersonation alone.
        """
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": f"{SITE_ROOT}/robots.txt",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    async def get_text(self, url: str) -> str:
        """Fetch a sitemap, transparently gunzipping .gz members.

        A 404 comes back as an empty string: numbered sitemap families end with
        a 404 rather than an empty document, so that is a stop condition for
        enumeration, not a failure.
        """
        last_error: Exception | None = None
        # Each edge refusal burns one fingerprint, so give document fetches at
        # least a full pass of the ladder before giving up.
        attempts = max(self.max_retries, len(TLS_PROFILES))
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(min(2**attempt + random.uniform(0, 1.5), 30))
            session = self._session_or_new()
            try:
                resp = await asyncio.to_thread(
                    session.get, url, headers=self._document_headers()
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.rotate_profile()
                continue

            if resp.status_code == 404:
                return ""
            if resp.status_code in (401, 403, 406, 429):
                # Static paths are edge-gated, so a refusal here is worth a new
                # fingerprint rather than a straight retry on the same session.
                last_error = GlintsBlocked(
                    f"HTTP {resp.status_code} for {url} on profile {self.profile}"
                )
                log.warning("HTTP %s for %s; rotating profile", resp.status_code, url)
                self.rotate_profile()
                continue
            if resp.status_code != 200:
                last_error = GlintsGraphQLError(f"HTTP {resp.status_code} for {url}")
                continue

            raw = resp.content or b""
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="replace")
            if self._looks_challenged(text):
                last_error = GlintsBlocked(f"challenge body for {url}")
                self.rotate_profile()
                continue
            return text

        raise last_error or GlintsGraphQLError(f"GET {url} failed")


LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)


def sitemap_locs(xml: str) -> list[str]:
    """Pull loc values out of a sitemap or sitemap index."""
    return [m.strip() for m in LOC_RE.findall(xml) if m.strip()]
