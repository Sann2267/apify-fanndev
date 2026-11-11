"""HTTP client for Facebook's public page HTML.

Deliberately plain. Recon on 2026-09-20 found no TLS-fingerprint gate on this
surface -- all 16 curl_cffi profiles returned 200 -- and no cookie or consent
handshake is needed, so the client does one GET per slug and keeps a retry
ladder only for transport failures and rate limiting.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    MAX_RETRIES,
    NAVIGATE_HEADERS,
    RETRY_DELAY_BASE,
    TLS_LADDER,
    TLS_PROFILE,
)


class BlockedError(RuntimeError):
    """Facebook refused the request in a way retrying did not fix."""


class FacebookClient:
    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        language: str = "en-US",
        timeout: int = 45,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.language = language
        self.timeout = timeout
        self.log = log
        self._session: AsyncSession | None = None

    def _build_session(self, profile: str) -> AsyncSession:
        kwargs: dict[str, Any] = {"impersonate": profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        return AsyncSession(**kwargs)

    async def __aenter__(self) -> "FacebookClient":
        self._session = self._build_session(self.profile)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def reset(self, profile: str | None = None) -> None:
        await self.close()
        if profile:
            self.profile = profile
        self._session = self._build_session(self.profile)

    async def fetch_about(self, slug: str) -> str:
        """Fetch a page's about tab and return the raw HTML.

        The about tab is used rather than the page root because it is the only
        one that carries the contact and category sections, and it costs the
        same single request.
        """
        return await self._get(f"{BASE_URL}/{slug}/about")

    async def _get(self, url: str) -> str:
        if self._session is None:
            raise RuntimeError("FacebookClient used outside its async context manager")
        headers = {**NAVIGATE_HEADERS, "accept-language": f"{self.language},en;q=0.9"}
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._session.get(url, headers=headers, allow_redirects=True)
            except Exception as exc:
                last_error = exc
                await self._backoff(attempt, f"transport error: {exc}")
                continue

            if resp.status_code == 200:
                return resp.text

            # Facebook answers 200 for missing pages, so a 404 here means the
            # URL shape itself was rejected -- retrying cannot help.
            if resp.status_code == 404:
                raise BlockedError("HTTP 404 -- Facebook rejected the URL shape")

            if resp.status_code in (403, 429, 503):
                last_error = BlockedError(f"HTTP {resp.status_code}")
                next_profile = TLS_LADDER[(attempt + 1) % len(TLS_LADDER)]
                await self._backoff(
                    attempt, f"HTTP {resp.status_code}; rotating to {next_profile}"
                )
                await self.reset(next_profile)
                continue

            last_error = BlockedError(f"HTTP {resp.status_code}")
            await self._backoff(attempt, f"HTTP {resp.status_code}")

        raise BlockedError(f"retries exhausted: {last_error}")

    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.4)
        if self.log:
            self.log.warning(f"retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s ({reason})")
        await asyncio.sleep(delay)
