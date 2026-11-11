"""HTTP transport for Google Hotels.

Google is the one target in this portfolio where the *exit IP* decides more
than the TLS profile does, so two behaviours are encoded here:

* A **TLS ladder**. The session remembers the profile that last won and keeps
  using it; on a block it walks the ladder rather than concluding "Google is
  closed" from a single profile (.ai/CLAUDE.md rule 2).
* A **size floor**. Google answers a challenge, a consent wall and an error
  page all with HTTP 200. Only the byte count separates them from content, so
  an unexpectedly small 200 is a failure here, never something to parse.
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
    b"/sorry/index",
    b"unusual traffic from your computer",
    b"enablejs",
    b"consent.google.com",
    b"CaptchaRedirect",
)


class BlockedUpstream(Exception):
    """Challenged, consent-walled, or an unusable body after the whole ladder."""


class EntityNotFound(Exception):
    """Google has no hotel under that entity id."""


class GoogleHotelsClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None):
        self._proxy_url = proxy_url
        self._ladder = list(TLS_LADDER)
        if profile:
            # Caller-pinned profile goes first but the rest stay available.
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]
        self._session: AsyncSession | None = None

    def _new_session(self, profile: str) -> AsyncSession:
        session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=90,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    async def get_html(self, url: str, min_bytes: int = MIN_PAGE_BYTES) -> tuple[str, str]:
        """Return ``(html, winning_tls_profile)``.

        Tries the remembered winner first, then the rest of the ladder. Each
        profile gets its own retry budget for plain network flakiness before
        the next profile is tried.
        """
        order = [self._winner] + [p for p in self._ladder if p != self._winner]
        failures: list[str] = []

        for profile in order:
            session = self._new_session(profile)
            try:
                html = await self._attempt(session, url, min_bytes)
            except (BlockedUpstream, EntityNotFound) as exc:
                if isinstance(exc, EntityNotFound):
                    await session.close()
                    raise
                failures.append(f"{profile}: {exc}")
                await session.close()
                continue
            else:
                await session.close()
                if profile != self._winner:
                    log.info(f"TLS profile {self._winner!r} blocked, {profile!r} won -- remembering it")
                    self._winner = profile
                return html, profile

        raise BlockedUpstream(
            "every TLS profile was blocked for "
            f"{url} -- {'; '.join(failures)}. Google gates on the exit IP as well as "
            "the fingerprint, so a residential proxy is the next lever, not another profile."
        )

    async def _attempt(self, session: AsyncSession, url: str, min_bytes: int) -> str:
        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await session.request("GET", url, allow_redirects=True)
            except Exception as exc:  # noqa: BLE001 -- network errors are retryable
                last = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            body = r.content or b""
            if r.status_code == 404:
                raise EntityNotFound(f"404 for {url}")
            if r.status_code in (301, 302) or any(m in body[:8192] for m in BLOCK_MARKERS):
                raise BlockedUpstream(f"challenge/consent redirect ({r.status_code})")
            if r.status_code >= 400:
                last = BlockedUpstream(f"HTTP {r.status_code}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if len(body) < min_bytes:
                # Google serves challenges with HTTP 200; size is the only tell.
                raise BlockedUpstream(
                    f"200 but only {len(body)} bytes (expected >{min_bytes}) -- "
                    f"that is a challenge or consent shell, not a hotel page"
                )
            return r.text or ""

        raise BlockedUpstream(f"exhausted {MAX_RETRIES} retries: {last!r}")

    async def close(self):
        if self._session is not None:
            await self._session.close()
