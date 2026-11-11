"""Async HTTP client: retries with exponential backoff, TLS and proxy rotation.

One client per target. Each holds a curl_cffi AsyncSession pinned to one proxy
session (so a target's pagination stays on one exit IP) and replaces it when
the transport fails or a gate appears.
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
    RESULT_BAD_PARAM,
    RESULT_BUSY,
    RESULT_OK,
    RESULT_PHOTO_NOT_FOUND,
    RETRY_STATUS,
    SITE,
    TLS_PROFILES,
)

log = logging.getLogger("snackvideo.client")


class SnackError(Exception):
    """Base for the outcomes callers route on."""


class SnackNotFound(SnackError):
    """SnackVideo answered definitively that the thing does not exist."""


class SnackApiError(SnackError):
    """The API answered with a non-OK result code that retrying will not fix."""

    def __init__(self, result: Any, message: str) -> None:
        super().__init__(f"result={result} {message}".strip())
        self.result = result


class SnackBlocked(SnackError):
    """Transport failure or a status that survived the whole retry ladder."""


def _backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SECS, BACKOFF_BASE_SECS * (2 ** attempt)) + random.uniform(0, 0.5)


class SnackClient:
    def __init__(
        self,
        proxy_configuration: Any = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT_SECS,
    ) -> None:
        self.proxy_configuration = proxy_configuration
        self.max_retries = max_retries
        self.timeout = timeout
        self._profile_idx = 0
        self._session: AsyncSession | None = None
        self.request_count = 0

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            proxy_url = None
            if self.proxy_configuration is not None:
                # A fresh session id = a fresh exit IP; reused for the whole
                # target so its cursor walk stays on one address.
                proxy_url = await self.proxy_configuration.new_url(
                    session_id="s" + secrets.token_hex(6)
                )
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
            log.info("Rotating TLS profile to %s", self.profile)
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
            self._session = None

    async def get_final_url(self, url: str) -> str:
        """Follow redirects (share short-links) and return where they land."""
        for attempt in range(self.max_retries):
            session = await self._get_session()
            try:
                r = await session.get(url, allow_redirects=True, headers={"Accept": "text/html"})
                self.request_count += 1
                return str(r.url)
            except RequestException as exc:
                log.warning("Resolving %s failed (%s), retry %d", url, exc, attempt + 1)
                await self.rotate()
                await asyncio.sleep(_backoff(attempt))
        raise SnackBlocked(f"Could not resolve {url}")

    async def api(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST one API call and return its JSON when result == 1.

        Raises SnackNotFound (result 205), SnackApiError (other final codes) or
        SnackBlocked (the retry ladder ran out).
        """
        last = "no attempt"
        bad_param_seen = False
        for attempt in range(self.max_retries):
            session = await self._get_session()
            try:
                r = await session.post(SITE + path, json=body)
                self.request_count += 1
            except RequestException as exc:
                last = f"transport: {exc}"
                log.warning("%s transport error (%s), retry %d/%d", path, exc, attempt + 1, self.max_retries)
                await self.rotate()
                await asyncio.sleep(_backoff(attempt))
                continue

            head = r.content[:4096] if r.content else b""
            if r.status_code == 403 or any(m in head for m in BLOCK_MARKERS):
                last = f"HTTP {r.status_code} gate"
                log.warning("%s looks gated (HTTP %s), rotating IP + TLS profile", path, r.status_code)
                await self.rotate(profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code in RETRY_STATUS:
                last = f"HTTP {r.status_code}"
                log.warning("%s HTTP %s, retry %d/%d", path, r.status_code, attempt + 1, self.max_retries)
                if r.status_code == 429:
                    await self.rotate()
                await asyncio.sleep(_backoff(attempt))
                continue
            if r.status_code != 200:
                raise SnackBlocked(f"{path} HTTP {r.status_code}")

            try:
                data = r.json()
            except ValueError:
                last = "non-JSON 200"
                log.warning("%s returned non-JSON body (%d bytes), rotating", path, len(r.content))
                await self.rotate(profile=True)
                await asyncio.sleep(_backoff(attempt))
                continue

            result = data.get("result")
            if result == RESULT_OK:
                return data
            if result == RESULT_PHOTO_NOT_FOUND:
                raise SnackNotFound(f"{path} result=205 (does not exist)")
            if result == RESULT_BUSY:
                last = "result=15 server busy"
                await asyncio.sleep(_backoff(attempt))
                continue
            if result == RESULT_BAD_PARAM and not bad_param_seen:
                # Deterministic for a rejected parameter, but give a network
                # blip one more chance before calling it final.
                bad_param_seen = True
                last = f"result=11 {data.get('error_msg', '')}"
                await asyncio.sleep(_backoff(attempt))
                continue
            raise SnackApiError(result, str(data.get("error_msg") or ""))

        raise SnackBlocked(f"{path} failed after {self.max_retries} attempts ({last})")
