"""HTTP client for 99.co: TLS impersonation, pacing, backoff, rotation."""

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
    BLOCK_MARKERS,
    CF_CHALLENGE_VALUE,
    CF_MITIGATED_HEADER,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    SITE_ROOT,
    TLS_PROFILES,
)

log = logging.getLogger("ninetynine.client")

RETRY_STATUS = (408, 425, 500, 502, 503, 504)


class NinetyNineBlocked(Exception):
    """Cloudflare answered with a managed challenge instead of the page."""


class NinetyNineChallengeWall(NinetyNineBlocked):
    """A challenge that rotating TLS profiles cannot get past.

    Raised once the whole ladder has been tried on one URL. On 99.co this is
    a real signal rather than a transport hiccup: deep Indonesian result pages
    (hlmn >= 10) are challenge-gated by policy, so callers treat this as
    "the site will not serve this slice" and stop paging cleanly instead of
    burning the retry budget.
    """


class NinetyNineNotFound(Exception):
    """The path is well formed but 99.co has nothing behind it."""


class NinetyNineClient:
    """One client per run, holding a curl_cffi session for the active profile.

    99.co gates on the TLS fingerprint (plain `requests` is 403 everywhere)
    and escalates to a Cloudflare managed challenge for some paths. The ladder
    deliberately excludes edge101 and chrome99_android, which were themselves
    challenged on the bare homepage during recon.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
        request_delay: float = DEFAULT_REQUEST_DELAY_SECS,
    ) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self._profile_idx = 0
        self._session: cr.Session | None = None
        self._last_request_at = 0.0
        self._pace_lock = asyncio.Lock()

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
        self._profile_idx += 1
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
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

    # -- pacing ------------------------------------------------------------

    async def _pace(self) -> None:
        """Keep a floor between requests.

        Cloudflare scores this origin more aggressively than a plain SSR site,
        and the pages are 1.5 MB, so a small delay costs proportionally little
        while keeping a long run from presenting as a burst.
        """
        if self.request_delay <= 0:
            return
        async with self._pace_lock:
            gap = time.monotonic() - self._last_request_at
            if gap < self.request_delay:
                await asyncio.sleep(self.request_delay - gap)
            self._last_request_at = time.monotonic()

    # -- headers -----------------------------------------------------------

    @staticmethod
    def _document_headers(referer: str | None) -> dict[str, str]:
        headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "upgrade-insecure-requests": "1",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none" if referer is None else "same-origin",
            "sec-fetch-user": "?1",
            "cache-control": "max-age=0",
        }
        if referer:
            headers["referer"] = referer
        return headers

    @staticmethod
    def _api_headers(referer: str) -> dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

    @staticmethod
    def _is_challenge(resp: Any, body: str) -> bool:
        """Detect a Cloudflare managed challenge.

        The response header is authoritative and cheap, so it is checked
        first; the body markers catch an interstitial served without it. The
        status code is deliberately NOT used on its own, because the same
        challenge arrives as 403 on deep ID pages and 429 on the homepage.
        """
        if (resp.headers.get(CF_MITIGATED_HEADER) or "").lower() == CF_CHALLENGE_VALUE:
            return True
        low = body[:4000].lower()
        return any(m in low for m in BLOCK_MARKERS)

    # -- core --------------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: Any = None,
        label: str = "",
    ) -> Any:
        label = label or url
        last_error: Exception | None = None
        challenges = 0
        # Give the ladder at least one full lap: a challenge is profile-shaped,
        # so stopping after fewer attempts than there are profiles would call
        # a wall on a slice another fingerprint might have been served.
        attempts = max(self.max_retries, len(TLS_PROFILES))

        for attempt in range(attempts):
            if attempt:
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info(
                    "Retry %d/%d for %s in %.1fs", attempt, attempts - 1, label, delay
                )
                await asyncio.sleep(delay)

            await self._pace()
            session = self._session_or_new()
            try:
                if method == "POST":
                    resp = await asyncio.to_thread(
                        session.post, url, headers=headers, data=json.dumps(json_body)
                    )
                else:
                    resp = await asyncio.to_thread(session.get, url, headers=headers)
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", label, exc)
                self.rotate_profile()
                continue

            body = resp.text or ""

            if self._is_challenge(resp, body):
                challenges += 1
                last_error = NinetyNineBlocked(
                    f"Cloudflare challenge on {label} "
                    f"(HTTP {resp.status_code}, profile {self.profile})"
                )
                if challenges >= len(TLS_PROFILES):
                    # Every profile drew the same challenge. That is policy,
                    # not luck -- let the caller stop rather than retry.
                    raise NinetyNineChallengeWall(
                        f"{label} is challenge-gated: all {len(TLS_PROFILES)} TLS "
                        f"profiles were served a Cloudflare managed challenge"
                    )
                self.rotate_profile()
                continue

            if resp.status_code == 404:
                raise NinetyNineNotFound(f"HTTP 404 on {label}")

            if resp.status_code in RETRY_STATUS:
                last_error = NinetyNineBlocked(f"HTTP {resp.status_code} on {label}")
                log.warning("HTTP %s on %s", resp.status_code, label)
                continue

            if resp.status_code == 429:
                last_error = NinetyNineBlocked(f"HTTP 429 on {label}")
                log.warning("Rate limited on %s; backing off and rotating", label)
                self.rotate_profile()
                continue

            return resp

        raise last_error or NinetyNineBlocked(
            f"{label} failed after {attempts} attempts"
        )

    async def get_page(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> tuple[str, str]:
        """GET an HTML page. Returns (final_url, body)."""
        url = path_or_url
        if url.startswith("/"):
            url = SITE_ROOT + url
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)

        resp = await self._request(
            "GET", url, headers=self._document_headers(referer), label=url
        )
        return str(resp.url), (resp.text or "")

    async def get_json(
        self, path: str, *, params: dict[str, Any] | None = None, referer: str
    ) -> Any:
        url = path if path.startswith("http") else SITE_ROOT + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        resp = await self._request(
            "GET", url, headers=self._api_headers(referer), label=path
        )
        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise NinetyNineBlocked(
                f"non-JSON body on {path} (HTTP {resp.status_code}): "
                f"{(resp.text or '')[:200]}"
            ) from exc
