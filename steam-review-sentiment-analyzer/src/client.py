"""Async HTTP client: paced per exit IP, retries with exponential backoff.

Steam has no WAF; what it has is a per-IP limiter on /appreviews/. So the
client paces those calls on each exit IP, and on a 429 it either takes a new
exit IP (proxy) or waits the window out (direct). Each client owns one proxy
session so a cursor walk stays on one address until it is rate limited.
"""

from __future__ import annotations

import asyncio
import logging
import random
import secrets
import time
from typing import Any

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from .constants import (
    BACKOFF_BASE_SECS,
    BACKOFF_CAP_SECS,
    BASE_HEADERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECS,
    OTHER_MIN_INTERVAL_SECS,
    RATE_LIMIT_COOLDOWN_SECS,
    RETRY_STATUS,
    REVIEWS_MIN_INTERVAL_SECS,
    TLS_PROFILES,
)

log = logging.getLogger("steam.client")


class SteamError(Exception):
    """Base for the outcomes callers route on."""


class SteamNotFound(SteamError):
    """Steam answered definitively that the thing does not exist."""


class SteamBlocked(SteamError):
    """Transport failure or a status that survived the whole retry ladder."""


def _backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SECS, BACKOFF_BASE_SECS * (2 ** attempt)) + random.uniform(0, 0.7)


class Pacer:
    """Minimum spacing between requests of one bucket on one exit IP."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = time.monotonic() + self.interval

    def penalise(self, secs: float) -> None:
        self._next = max(self._next, time.monotonic() + secs)


class Pacers:
    # Undocumented test hook (input `debugReviewsIntervalSecs`): 0 removes the
    # pacing so the rate-limit / IP-rotation path can be exercised on purpose.
    reviews_interval = REVIEWS_MIN_INTERVAL_SECS

    def __init__(self) -> None:
        self.reviews = Pacer(Pacers.reviews_interval)
        self.other = Pacer(OTHER_MIN_INTERVAL_SECS)


class SteamClient:
    def __init__(
        self,
        proxy_configuration: Any = None,
        shared_pacers: Pacers | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT_SECS,
    ) -> None:
        self.proxy_configuration = proxy_configuration
        self.max_retries = max_retries
        self.timeout = timeout
        # Direct runs share ONE IP across all workers, so they must share the
        # pacers; proxied clients get their own per-session pacers.
        self._shared = shared_pacers
        self.pacers = shared_pacers or Pacers()
        self._profile_idx = random.randrange(len(TLS_PROFILES))
        self._session: AsyncSession | None = None
        self.request_count = 0

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            proxy_url = None
            if self.proxy_configuration is not None:
                proxy_url = await self.proxy_configuration.new_url(session_id="s" + secrets.token_hex(6))
            self._session = AsyncSession(
                impersonate=self.profile,
                timeout=self.timeout,
                proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
                headers=BASE_HEADERS,
            )
        return self._session

    async def rotate(self, *, profile: bool = False) -> None:
        """Drop the session (new exit IP next time); optionally the TLS profile too."""
        if profile:
            self._profile_idx += 1
        await self.close()
        if self._shared is None:
            self.pacers = Pacers()  # new IP, fresh bucket

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
            self._session = None

    async def _rate_limited(self, pacer: Pacer, attempt: int) -> None:
        if self.proxy_configuration is not None:
            await self.rotate()
            await asyncio.sleep(_backoff(min(attempt, 2)))
        else:
            wait = RATE_LIMIT_COOLDOWN_SECS + 10 * min(attempt, 3) + random.uniform(0, 3)
            log.info("Rate limited by Steam (no proxy) - waiting %.0f s", wait)
            pacer.penalise(wait)

    async def request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        bucket: str = "other",
        expect_json: bool = True,
    ) -> Any:
        """GET url; return parsed JSON (or text). Raises SteamBlocked when retries run out."""
        pacer = self.pacers.reviews if bucket == "reviews" else self.pacers.other
        last = "no attempt"
        for attempt in range(self.max_retries):
            await pacer.wait()
            session = await self._get_session()
            try:
                r = await session.get(url, params=params)
                self.request_count += 1
            except RequestException as exc:
                last = f"transport: {exc}"
                log.warning("%s transport error (%s), retry %d/%d", url, exc, attempt + 1, self.max_retries)
                await self.rotate(profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue

            body = r.content or b""
            if r.status_code == 429 or (r.status_code == 200 and body[:40].startswith(b'{"success":84')):
                last = "HTTP 429 rate limit"
                log.warning("%s rate limited, retry %d/%d%s", url.split("?")[0], attempt + 1, self.max_retries,
                            " - switching to a new proxy IP" if self.proxy_configuration is not None else "")
                await self._rate_limited(pacer, attempt)
                continue
            if r.status_code in RETRY_STATUS or r.status_code == 403:
                last = f"HTTP {r.status_code}"
                log.warning("%s HTTP %s, retry %d/%d", url, r.status_code, attempt + 1, self.max_retries)
                await self.rotate(profile=r.status_code == 403)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code == 404:
                raise SteamNotFound(f"{url} HTTP 404")
            if r.status_code != 200:
                raise SteamBlocked(f"{url} HTTP {r.status_code}")
            if not expect_json:
                return r.text
            try:
                return r.json()
            except ValueError:
                last = f"non-JSON 200 ({len(body)} bytes)"
                log.warning("%s returned non-JSON body, retry %d/%d", url, attempt + 1, self.max_retries)
                await self.rotate(profile=True)
                await asyncio.sleep(_backoff(attempt))
        raise SteamBlocked(f"{url.split('?')[0]} failed after {self.max_retries} attempts ({last})")
