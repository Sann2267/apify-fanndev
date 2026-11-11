"""HTTP transport for medium.com.

Medium sits behind Cloudflare, so the client keeps a TLS ladder and remembers
the profile that last won rather than concluding the source is closed from one
failure (`.ai/CLAUDE.md` rule 2). ``chrome124`` answered 200 on every recon
request; ``chrome131`` is deliberately absent from the ladder because it is
widely blocklisted in 2026.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    MIN_PAGE_BYTES,
    RETRY_DELAY_BASE,
    TLS_LADDER,
)

log = logging.getLogger(__name__)

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"Attention Required",
    b"Access denied",
)


class Blocked(Exception):
    """Challenged, or an unusable body after the whole ladder."""


class NotFound(Exception):
    """No such tag, author, publication or post."""


class MediumClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None):
        self._proxy_url = proxy_url
        self._ladder = list(TLS_LADDER)
        if profile:
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]

    def _new_session(self, profile: str) -> AsyncSession:
        session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=75,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    async def get(self, url: str, min_bytes: int = MIN_PAGE_BYTES) -> tuple[str, str]:
        """Return ``(body, winning_tls_profile)``."""
        order = [self._winner] + [p for p in self._ladder if p != self._winner]
        failures: list[str] = []

        for profile in order:
            session = self._new_session(profile)
            try:
                body = await self._attempt(session, url, min_bytes)
            except NotFound:
                await session.close()
                raise
            except Blocked as exc:
                failures.append(f"{profile}: {exc}")
                await session.close()
                continue
            else:
                await session.close()
                if profile != self._winner:
                    log.info(f"TLS {self._winner!r} blocked, {profile!r} won -- remembering it")
                    self._winner = profile
                return body, profile

        raise Blocked(f"every TLS profile was blocked for {url} -- {'; '.join(failures)}")

    async def _attempt(self, session: AsyncSession, url: str, min_bytes: int) -> str:
        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await session.request("GET", url, allow_redirects=True)
            except Exception as exc:  # noqa: BLE001 -- network errors are retryable
                last = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            raw = r.content or b""
            if r.status_code == 404:
                raise NotFound(f"404 for {url}")
            if any(m in raw[:8192] for m in BLOCK_MARKERS):
                raise Blocked(f"challenge page ({r.status_code})")
            if r.status_code == 403:
                raise Blocked("403")
            if r.status_code >= 400:
                last = Blocked(f"HTTP {r.status_code}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if len(raw) < min_bytes:
                raise Blocked(
                    f"200 but only {len(raw)} bytes (expected >{min_bytes}) -- an error or "
                    f"challenge shell, not content"
                )
            return r.text or ""

        raise Blocked(f"exhausted {MAX_RETRIES} retries: {last!r}")
