"""Async HTTP client: exponential backoff, search-host rate limiter, TLS-profile and exit-IP rotation.

One shared client per run. Nothing is stateful (no cookies, no cursors tied to
an IP), so one connection pool serves every task; rotation swaps the pool.
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
    BLOCK_MARKERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECS,
    RATE_LIMIT_COOLDOWN_SECS,
    RATE_LIMIT_MARKER,
    RETRY_STATUS,
    SEARCH_BUCKET_CAPACITY,
    SEARCH_HOST,
    SEARCH_REFILL_SECS,
    TLS_PROFILES,
)

log = logging.getLogger("steam.client")


class SteamError(Exception):
    """Base for outcomes callers route on."""


class NotFound(SteamError):
    """Upstream answered definitively that the thing does not exist."""


class Blocked(SteamError):
    """Transport failure, gate or bad status that survived the whole retry ladder."""


def _backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SECS, BACKOFF_BASE_SECS * (2 ** attempt)) + random.uniform(0, 0.5)


class TokenBucket:
    """Steam's /search/results/ limit is per IP: ~40 burst, then ~1 call / 2.5 s."""

    def __init__(self, capacity: int, refill_secs: float) -> None:
        self.capacity = capacity
        self.refill_secs = refill_secs
        self.tokens = float(capacity)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def take(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) / self.refill_secs)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) * self.refill_secs)

    def reset(self) -> None:
        """New exit IP -> fresh budget."""
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()


class Response:
    """What callers need from a response, detached from the session."""

    def __init__(self, status: int, url: str, content: bytes) -> None:
        self.status = status
        self.url = url
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")


class SteamClient:
    def __init__(self, proxy_configuration: Any = None, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.proxy_configuration = proxy_configuration
        self.max_retries = max_retries
        self._profile_idx = 0
        self._session: AsyncSession | None = None
        self._lock = asyncio.Lock()
        self.search_bucket = TokenBucket(SEARCH_BUCKET_CAPACITY, SEARCH_REFILL_SECS)
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
                    max_clients=16,
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
            if self.proxy_configuration is not None:
                self.search_bucket.reset()
        try:
            await stale.close()
        except Exception:  # noqa: BLE001 - closing must not mask the real error
            pass

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    async def fetch(self, url: str, params: dict[str, Any] | None = None, *, want_json: bool = False) -> Any:
        """GET with retries. Returns parsed JSON (want_json) or a Response."""
        is_search = SEARCH_HOST in url
        last = "no attempt"
        for attempt in range(self.max_retries):
            if is_search:
                await self.search_bucket.take()
            session = await self._get_session()
            try:
                r = await session.get(url, params=params, allow_redirects=True)
                self.request_count += 1
            except RequestException as exc:
                last = f"transport: {exc}"
                log.warning("%s transport error (%s), retry %d/%d", url, exc, attempt + 1, self.max_retries)
                await self.rotate(session)
                await asyncio.sleep(_backoff(attempt))
                continue

            head = r.content[:4096] if r.content else b""
            if r.status_code == 429 or RATE_LIMIT_MARKER in head:
                # Per-IP rate limit (no WAF). A new exit IP clears it at once;
                # without a proxy the lockout (~20 s) must be waited out.
                self.rate_limited += 1
                last = "HTTP 429 rate limit"
                if self.proxy_configuration is not None:
                    log.warning("%s rate-limited (429), rotating exit IP (retry %d/%d)", url, attempt + 1, self.max_retries)
                    await self.rotate(session)
                    await asyncio.sleep(_backoff(0))
                else:
                    wait = RATE_LIMIT_COOLDOWN_SECS + random.uniform(0, 5)
                    log.warning("%s rate-limited (429), no proxy - cooling down %.0f s (retry %d/%d)", url, wait, attempt + 1, self.max_retries)
                    await asyncio.sleep(wait)
                continue
            if r.status_code == 403 or (r.status_code != 200 and any(m in head for m in BLOCK_MARKERS)):
                last = f"HTTP {r.status_code} gate"
                log.warning("%s looks gated (HTTP %s), rotating IP + TLS profile", url, r.status_code)
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code == 404:
                raise NotFound(f"HTTP 404 for {url}")
            if r.status_code in RETRY_STATUS:
                last = f"HTTP {r.status_code}"
                log.warning("%s HTTP %s, retry %d/%d", url, r.status_code, attempt + 1, self.max_retries)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code == 400:
                raise NotFound(f"HTTP 400 (rejected request) for {url}")
            if r.status_code != 200:
                raise Blocked(f"{url} HTTP {r.status_code}")

            if any(m in head for m in BLOCK_MARKERS[:3]):  # challenge page served as 200
                last = "challenge page with HTTP 200"
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue
            if not want_json:
                return Response(r.status_code, str(r.url), r.content)
            try:
                return r.json()
            except ValueError:
                last = f"non-JSON 200 ({len(r.content)} bytes)"
                log.warning("%s returned a non-JSON body, retrying", url)
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue

        raise Blocked(f"{url} failed after {self.max_retries} attempts ({last})")

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return await self.fetch(url, params, want_json=True)

    async def get_page(self, url: str, params: dict[str, Any] | None = None) -> Response:
        return await self.fetch(url, params)
