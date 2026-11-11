"""Async HTTP client: exponential backoff, TLS-profile and exit-IP rotation.

One shared client per run. Nothing here is stateful (no cookies, no cursors
tied to an IP), so a single connection pool serves every task; rotation just
swaps the pool. HTML pages pass through a separate, smaller semaphore because
steamcommunity rate-limits HTML per IP while leaving XML/API alone.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import secrets
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from .constants import (
    AKAMAI_PENALTY_WAIT_SECS,
    BACKOFF_BASE_SECS,
    BACKOFF_CAP_SECS,
    BASE_HEADERS,
    BLOCK_MARKERS,
    DEFAULT_HTML_CONCURRENCY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECS,
    HTML_429_WAIT_SECS,
    RETRY_STATUS,
    TLS_PROFILES,
)

log = logging.getLogger("steam.client")


class SteamError(Exception):
    """Base for outcomes callers route on."""


class NotFound(SteamError):
    """Upstream answered HTTP 404."""


class Blocked(SteamError):
    """Transport failure, gate or bad status that survived the whole retry ladder."""


@dataclass
class Page:
    url: str  # final URL after redirects - callers route on it (stats redirects)
    text: str
    status: int


def _backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SECS, BACKOFF_BASE_SECS * (2 ** attempt)) + random.uniform(0, 0.5)


class SteamClient:
    def __init__(self, proxy_configuration: Any = None, max_retries: int = DEFAULT_MAX_RETRIES,
                 concurrency: int = 8, html_concurrency: int = DEFAULT_HTML_CONCURRENCY) -> None:
        self.proxy_configuration = proxy_configuration
        self.max_retries = max_retries
        self._profile_idx = 0
        self._session: AsyncSession | None = None
        # Rotated-out pools are closed only at the end of the run: closing one
        # while sibling tasks still have requests in flight on it makes those
        # requests come back as status 0.
        self._retired: list[AsyncSession] = []
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(concurrency)
        self._html_sem = asyncio.Semaphore(html_concurrency)
        self.request_count = 0
        self.rate_limited = 0

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    async def _get_session(self) -> AsyncSession:
        async with self._lock:
            if self._session is None:
                proxy_url = None
                if self.proxy_configuration is not None:
                    proxy_url = await self.proxy_configuration.new_url(session_id="s" + secrets.token_hex(6))
                self._session = AsyncSession(
                    impersonate=self.profile,
                    timeout=DEFAULT_TIMEOUT_SECS,
                    proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
                    headers=BASE_HEADERS,
                    max_clients=24,
                )
            return self._session

    async def rotate(self, stale: AsyncSession, *, profile: bool = False) -> None:
        """Replace the pool (new exit IP when proxied), optionally the TLS profile too.

        `stale` guards against N concurrent failures rotating N times in a row.
        """
        async with self._lock:
            if self._session is not stale:
                return
            if profile:
                self._profile_idx += 1
                log.info("Rotating TLS profile to %s", self.profile)
            self._session = None
            self._retired.append(stale)

    async def close(self) -> None:
        pools = self._retired + ([self._session] if self._session is not None else [])
        self._retired, self._session = [], None
        for s in pools:
            try:
                await s.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass

    async def _request(self, url: str, params: dict[str, Any] | None, *, html: bool) -> Page:
        sem = self._html_sem if html else self._sem
        last = "no attempt"
        for attempt in range(self.max_retries):
            async with sem:
                session = await self._get_session()
                try:
                    r = await session.get(url, params=params, allow_redirects=True)
                    self.request_count += 1
                except RequestException as exc:
                    r = None
                    last = f"transport: {exc}"
                if r is not None and r.status_code == 0:
                    r = None
                    last = "transport: empty response (status 0)"
                if r is None:
                    log.warning("%s transport error (%s), retry %d/%d", url, last, attempt + 1, self.max_retries)
                    await self.rotate(session)
                    await asyncio.sleep(_backoff(attempt))
                    continue
                if r.status_code == 429:
                    self.rate_limited += 1
                    last = "HTTP 429 rate limit"
                    if self.proxy_configuration is not None:
                        await self.rotate(session)
                        wait = _backoff(attempt)
                    else:
                        # Hold the semaphore while waiting: the whole HTML bucket is
                        # exhausted for this IP, so other HTML tasks must wait too.
                        wait = HTML_429_WAIT_SECS if html else _backoff(attempt + 2)
                    log.warning("%s rate-limited (429), waiting %.0f s (retry %d/%d)", url, wait, attempt + 1, self.max_retries)
                    await asyncio.sleep(wait)
                    continue

            head = r.content[:4096] if r.content else b""
            if r.status_code == 403 or (r.status_code != 200 and any(m in head for m in BLOCK_MARKERS)):
                # Hammering steamcommunity escalates the 429 into an Akamai 403
                # 'Access Denied' (414 B, server AkamaiGHost). The penalty is keyed
                # on IP + TLS fingerprint: chrome124 got 403 while safari17_0 and
                # firefox133 got 200 from the same IP at the same moment, and it
                # lifted ~20 s later (recon 2026-10-11). So rotate the profile (and
                # the IP when proxied) at once, and only wait it out if it persists.
                self.rate_limited += 1
                last = f"HTTP {r.status_code} gate"
                wait = _backoff(attempt) if self.proxy_configuration is not None or attempt < 2 else AKAMAI_PENALTY_WAIT_SECS
                log.warning("%s looks gated (HTTP %s), rotating IP + TLS profile, waiting %.0f s", url, r.status_code, wait)
                await self.rotate(session, profile=True)
                await asyncio.sleep(wait)
                continue
            if r.status_code == 404:
                raise NotFound(f"HTTP 404 {url}")
            if r.status_code in RETRY_STATUS:
                last = f"HTTP {r.status_code}"
                log.warning("%s HTTP %s, retry %d/%d", url, r.status_code, attempt + 1, self.max_retries)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code != 200:
                raise Blocked(f"{url} HTTP {r.status_code}")
            if any(m in head for m in BLOCK_MARKERS[:3]):  # challenge served as 200
                last = "challenge page with HTTP 200"
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue
            return Page(url=str(r.url), text=r.text, status=r.status_code)

        raise Blocked(f"{url} failed after {self.max_retries} attempts ({last})")

    async def get(self, url: str, params: dict[str, Any] | None = None, *, html: bool = False) -> Page:
        return await self._request(url, params, html=html)

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        page = await self._request(url, params, html=False)
        try:
            return json.loads(page.text)
        except ValueError as exc:
            raise Blocked(f"{url} returned non-JSON ({len(page.text)} chars)") from exc
