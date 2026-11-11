"""HTTP client for Etsy: TLS impersonation, pacing, DataDome detection, rotation."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    BLOCK_MARKERS,
    DATADOME_HEADER,
    DATADOME_SERVER,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    SITE_ROOT,
    TLS_PROFILES,
)

log = logging.getLogger("etsy.client")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)


class EtsyBlocked(Exception):
    """DataDome answered with its interstitial stub instead of the page."""


class EtsyChallengeWall(EtsyBlocked):
    """Every TLS profile drew the interstitial on one URL.

    On Etsy this is a real signal rather than a transport hiccup. The three
    things that reliably cause it -- a bare `/shop/` path, a wrong or missing
    listing slug, and a `/search?q=` product query -- are all decided by the
    URL, so once the whole ladder has been spent the answer will not change by
    trying again. Callers treat it as "this URL is not servable" and move on
    with a diagnostic row rather than burning the run's budget.
    """


class EtsyNotFound(Exception):
    """The path is well formed but Etsy has nothing behind it."""


class EtsyClient:
    """One client per run, holding a curl_cffi session for the active profile.

    The session matters beyond connection reuse: Etsy hands out `uaid` and
    `datadome` cookies on the first served page, and carrying them makes the
    following requests look like continued browsing rather than a series of
    cold entries.
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
        self.blocked_count = 0
        self.request_count = 0

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
        self.close()
        log.warning("Rotated TLS profile to %s", self.profile)
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
        """Keep a floor between requests.

        Etsy pages are 200 KB to 1 MB, so a couple of seconds costs little next
        to the transfer, and DataDome scores request rate: during recon a burst
        of about 30 requests was enough to move one address from "served" to
        "challenged on every listing page" for the rest of the session.
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
        """Only the headers a navigation would add on top of the impersonation.

        curl_cffi already sends the impersonated browser's own header set in
        its own order, and DataDome checks that set against the TLS
        fingerprint. Overriding accept / accept-language / sec-ch-* here would
        break the very consistency the impersonation buys, so this adds a
        referer and nothing else.
        """
        return {"referer": referer} if referer else {}

    @staticmethod
    def _is_challenge(resp: Any, body: str) -> bool:
        if (resp.headers.get("server") or "").lower() == DATADOME_SERVER:
            # DataDome only answers the request itself when it is blocking it;
            # a served page comes back from Etsy's own Apache/Fastly stack.
            return True
        if resp.status_code == 403 and resp.headers.get(DATADOME_HEADER):
            return True
        low = body[:3000].lower()
        return any(m in low for m in BLOCK_MARKERS)

    # -- core --------------------------------------------------------------

    async def _request(self, url: str, *, referer: str | None, label: str) -> Any:
        last_error: Exception | None = None
        challenges = 0
        # Give the ladder at least one full lap: the interstitial is
        # profile-shaped, so stopping earlier than there are profiles would
        # call a wall on a URL another fingerprint might have been served.
        attempts = max(self.max_retries, len(TLS_PROFILES))

        for attempt in range(attempts):
            if attempt:
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info("Retry %d/%d for %s in %.1fs", attempt, attempts - 1, label, delay)
                await asyncio.sleep(delay)

            await self._pace()
            session = self._session_or_new()
            self.request_count += 1
            try:
                resp = await asyncio.to_thread(
                    session.get, url, headers=self._document_headers(referer)
                )
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", label, exc)
                self.rotate_profile()
                continue

            body = resp.text or ""

            if self._is_challenge(resp, body):
                challenges += 1
                self.blocked_count += 1
                last_error = EtsyBlocked(
                    f"DataDome interstitial on {label} "
                    f"(HTTP {resp.status_code}, profile {self.profile})"
                )
                if challenges >= len(TLS_PROFILES):
                    raise EtsyChallengeWall(
                        f"{label} is challenge-gated: all {len(TLS_PROFILES)} TLS "
                        f"profiles were served the DataDome interstitial"
                    )
                self.rotate_profile()
                continue

            if resp.status_code == 404:
                raise EtsyNotFound(f"HTTP 404 on {label}")

            if resp.status_code in RETRY_STATUS:
                last_error = EtsyBlocked(f"HTTP {resp.status_code} on {label}")
                log.warning("HTTP %s on %s", resp.status_code, label)
                if resp.status_code == 429:
                    self.rotate_profile()
                continue

            return resp

        raise last_error or EtsyBlocked(f"{label} failed after {attempts} attempts")

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
        resp = await self._request(url, referer=referer, label=url)
        return str(resp.url), (resp.text or "")
