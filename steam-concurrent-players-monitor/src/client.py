"""Async HTTP client: exponential backoff, TLS-profile and exit-IP rotation.

One shared client per run. None of the surfaces is stateful (no cookies, no
cursors tied to an IP), so a single connection pool serves every concurrent
task; rotation simply swaps the pool.
"""

from __future__ import annotations

import asyncio
import logging
import random
import secrets
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
    RETRY_STATUS,
    TLS_PROFILES,
)

log = logging.getLogger("steam.client")


class SteamError(Exception):
    """Base for outcomes callers route on."""


class NotFound(SteamError):
    """Upstream answered definitively that the thing does not exist (HTTP 404)."""


class Blocked(SteamError):
    """Transport failure, gate or bad status that survived the whole retry ladder."""


def _backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SECS, BACKOFF_BASE_SECS * (2 ** attempt)) + random.uniform(0, 0.5)


class SteamClient:
    def __init__(self, proxy_configuration: Any = None, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.proxy_configuration = proxy_configuration
        self.max_retries = max_retries
        self._profile_idx = 0
        self._session: AsyncSession | None = None
        self._lock = asyncio.Lock()
        self.request_count = 0

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

    async def _request(self, url: str, params: dict[str, Any] | None, *, want_json: bool) -> Any:
        last = "no attempt"
        for attempt in range(self.max_retries):
            session = await self._get_session()
            try:
                r = await session.get(url, params=params)
                self.request_count += 1
            except RequestException as exc:
                last = f"transport: {exc}"
                log.warning("%s transport error (%s), retry %d/%d", url, exc, attempt + 1, self.max_retries)
                await self.rotate(session)
                await asyncio.sleep(_backoff(attempt))
                continue

            head = r.content[:4096] if r.content else b""
            if r.status_code == 403 or (r.status_code != 200 and any(m in head for m in BLOCK_MARKERS)):
                last = f"HTTP {r.status_code} gate"
                log.warning("%s looks gated (HTTP %s), rotating IP + TLS profile", url, r.status_code)
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code == 404:
                body = None
                if want_json:
                    try:
                        body = r.json()
                    except ValueError:
                        pass
                raise NotFound(f"HTTP 404 {body if body is not None else ''}".strip())
            if r.status_code in RETRY_STATUS:
                last = f"HTTP {r.status_code}"
                log.warning("%s HTTP %s, retry %d/%d", url, r.status_code, attempt + 1, self.max_retries)
                if r.status_code == 429:
                    await self.rotate(session)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code != 200:
                raise Blocked(f"{url} HTTP {r.status_code}")

            if not want_json:
                if any(m in head for m in BLOCK_MARKERS[:3]):  # Cloudflare challenge served as 200
                    last = "challenge page with HTTP 200"
                    await self.rotate(session, profile=True)
                    await asyncio.sleep(_backoff(attempt))
                    continue
                return r.text
            try:
                return r.json()
            except ValueError:
                last = f"non-JSON 200 ({len(r.content)} bytes)"
                log.warning("%s returned non-JSON body, rotating", url)
                await self.rotate(session, profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue

        raise Blocked(f"{url} failed after {self.max_retries} attempts ({last})")

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(url, params, want_json=True)

    async def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        return await self._request(url, params, want_json=False)
