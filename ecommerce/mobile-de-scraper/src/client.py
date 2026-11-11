"""HTTP client for the mobile.de consumer API.

The gate is a single thing: **TLS fingerprint**. Recon on 2026-09-22 found
that a plain `requests` call to the very same URL returns Akamai's 7.7 KB
"Zugriff verweigert / Access denied" page, while every `curl_cffi`
impersonation profile returns 200 -- cold, with no warm-up request, no cookie
jar, no `x-mobile-vi` token and no custom headers at all.

That is unusual enough to be worth stating plainly, because it decides how
this whole actor is built: there is nothing to harvest, nothing to refresh and
nothing to keep in sync with the site. If this actor ever starts returning the
denial page, the fix is a newer impersonation profile, not a token hunt.

The client still sends the app's own headers (`x-mobile-device-type`,
`accept-language`). They are not required today, but they cost nothing and
make the traffic look like what the endpoint actually serves.
"""

from __future__ import annotations

import asyncio
import logging
import random
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    API_ROOT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    RATE_LIMIT_COOLDOWN_SECS,
    SITE_ROOT,
    TLS_PROFILES,
)

log = logging.getLogger("mobilede.client")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)

# Akamai's denial page is text/html and always carries this title. Status is
# 403, but matching the body too means a future soft-block (200 + challenge
# body, which is how several other WAFs in this portfolio behave) is still
# caught instead of being parsed as data.
BLOCK_MARKERS = ("Zugriff verweigert", "Access denied", "Error Reference")


class MobileDeError(Exception):
    """Base for outcomes callers route on."""


class MobileDeBlocked(MobileDeError):
    """Akamai refused the request -- TLS profile not accepted, or the IP is burnt.

    Raised after the profile ladder is exhausted. Retrying the same way cannot
    fix it; the answer is a newer `curl_cffi` profile or a different exit IP.
    """


class MobileDeNotFound(MobileDeError):
    """The ad, seller or page genuinely does not exist. Final answer."""


class MobileDeBadRequest(MobileDeError):
    """The API rejected the request shape (400).

    On this API that nearly always means the `url` parameter was not a
    root-relative suchen.mobile.de path -- an absolute www.mobile.de URL
    returns 400 "SVC API request failed".
    """


class MobileDeClient:
    """Session wrapper: TLS impersonation, retries, pacing, block detection."""

    def __init__(
        self,
        proxy_url: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        delay: float = DEFAULT_REQUEST_DELAY_SECS,
        language: str = "de",
    ) -> None:
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay
        self.language = language
        self._profile_idx = 0
        self._session: cr.AsyncSession | None = None
        self.requests_made = 0

    # -- session ------------------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[min(self._profile_idx, len(TLS_PROFILES) - 1)]

    def _build_session(self) -> cr.AsyncSession:
        kwargs: dict[str, Any] = {
            "impersonate": self.profile,
            "timeout": self.timeout,
        }
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        session = cr.AsyncSession(**kwargs)
        session.headers.update(
            {
                "accept": "application/json, text/plain, */*",
                "accept-language": f"{self.language}-DE,{self.language};q=0.9,en;q=0.8",
                "content-type": "application/json",
                "x-mobile-device-type": "DESKTOP",
                "referer": f"{SITE_ROOT}/",
                "origin": SITE_ROOT,
            }
        )
        return session

    async def _ensure_session(self) -> cr.AsyncSession:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    async def _rotate_profile(self) -> None:
        """Move to the next TLS profile and rebuild the session.

        Only called when a response looks like Akamai's denial page. Rotating
        on an ordinary 5xx would burn the ladder on a transient fault.
        """
        self._profile_idx += 1
        await self.close()
        if self._profile_idx < len(TLS_PROFILES):
            log.warning("Rotating TLS impersonation profile -> %s", self.profile)

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001 - closing must never fail a run
                pass
            self._session = None

    # -- request ------------------------------------------------------------

    @staticmethod
    def _looks_blocked(status: int, text: str) -> bool:
        if status == 403:
            return True
        # A 200 carrying the challenge body would otherwise be parsed as data.
        head = text[:4000]
        return any(marker in head for marker in BLOCK_MARKERS)

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET an API path and return parsed JSON, or raise a typed error.

        `path` is relative to API_ROOT, e.g. "search/srp".
        """
        url = f"{API_ROOT}/{path.lstrip('/')}"
        if params:
            # safe="" so ':' in range filters (p=:20000) and '/' inside the
            # `url` value are percent-encoded exactly as the web app sends them.
            query = urllib.parse.urlencode(
                params, quote_via=urllib.parse.quote, safe=""
            )
            url = f"{url}?{query}"

        attempts = self.max_retries + 1
        last_detail = ""
        for attempt in range(1, attempts + 1):
            if self.delay:
                await asyncio.sleep(self.delay * random.uniform(0.7, 1.3))
            session = await self._ensure_session()
            try:
                resp = await session.get(url)
            except Exception as exc:  # noqa: BLE001 - network faults are retryable
                last_detail = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "Request failed (%s/%s) %s -- %s",
                    attempt, attempts, path, last_detail,
                )
                await asyncio.sleep(min(2 ** attempt, 20))
                continue

            self.requests_made += 1
            status = resp.status_code
            text = resp.text or ""

            if self._looks_blocked(status, text):
                last_detail = f"HTTP {status}, Akamai denial page ({len(text)} bytes)"
                log.warning(
                    "Blocked on profile %s (%s/%s): %s",
                    self.profile, attempt, attempts, last_detail,
                )
                await self._rotate_profile()
                if self._profile_idx >= len(TLS_PROFILES):
                    raise MobileDeBlocked(
                        "Akamai refused every TLS profile in the ladder. Either "
                        "curl_cffi's profiles have gone stale or this exit IP is "
                        f"burnt. Last: {last_detail}"
                    )
                continue

            if status == 404:
                raise MobileDeNotFound(f"HTTP 404 for {path}")

            if status == 400:
                raise MobileDeBadRequest(f"HTTP 400 for {path}: {text[:200]}")

            if status in RETRY_STATUS:
                last_detail = f"HTTP {status}"
                backoff = (
                    RATE_LIMIT_COOLDOWN_SECS if status == 429 else min(2 ** attempt, 20)
                )
                log.warning(
                    "Retryable %s on %s (%s/%s); sleeping %.0fs",
                    status, path, attempt, attempts, backoff,
                )
                await asyncio.sleep(backoff)
                continue

            if status >= 400:
                raise MobileDeError(f"HTTP {status} for {path}: {text[:200]}")

            try:
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                # A 200 that is not JSON is a shape change, not a transient
                # fault -- fail loud rather than emit an empty record.
                raise MobileDeError(
                    f"200 OK but body is not JSON for {path} "
                    f"({type(exc).__name__}; first 200 bytes: {text[:200]!r})"
                ) from exc

        raise MobileDeError(
            f"Giving up on {path} after {attempts} attempts: {last_detail}"
        )
