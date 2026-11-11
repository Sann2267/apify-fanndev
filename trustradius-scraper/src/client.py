"""HTTP transport for trustradius.com.

One host, one gate: Cloudflare, answering on the TLS fingerprint (see the
matrix in constants.py). The client keeps a ladder of profiles and remembers
which one answered, instead of pinning one and failing a run it could have
survived.

A challenge is detected by body marker as well as status: Cloudflare's
interstitial arrives as a 403 with ``Just a moment...`` in the first bytes.
On a challenge the client also asks the proxy for a fresh session (a new exit
IP), because on a residential pool the verdict often belongs to the IP, not to
the fingerprint.

Two payload kinds come back:

* modern pages (Next.js App Router) are fetched with ``RSC: 1`` and yield a
  flight stream; if the answer turns out to be HTML (a CDN that ignores the
  header), the stream is recovered from the embedded ``self.__next_f`` chunks;
* legacy pages (single review, competitors) are plain HTML with a JSON blob.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable

from curl_cffi.requests import AsyncSession

from src.constants import (
    BLOCK_MARKERS,
    CHALLENGE_RETRIES,
    DEFAULT_HEADERS,
    HTML_HEADERS,
    LADDER_ROUND_DELAY,
    LADDER_ROUNDS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    RSC_HEADERS,
    TLS_LADDER,
)
from src.flight import stream_from_html

log = logging.getLogger(__name__)

ProxyFactory = Callable[[], Awaitable[str | None]]


class Blocked(Exception):
    """Challenged by Cloudflare on every profile, or the server kept failing."""


class NotFound(Exception):
    """404 -- no such product, category, review or comparison."""


def _backoff(attempt: int, base: float = RETRY_DELAY_BASE) -> float:
    return base * (2**attempt) + random.uniform(0, base)


class TrustRadiusClient:
    def __init__(self, proxy_factory: ProxyFactory | None = None, ladder: list[str] | None = None):
        self._proxy_factory = proxy_factory
        self._ladder = list(ladder or TLS_LADDER)
        self._winner = self._ladder[0]
        self._session: AsyncSession | None = None
        self._session_profile: str | None = None
        self._stale: list[AsyncSession] = []
        self.requests = 0
        self.challenges = 0
        self.bytes = 0

    # -- session -----------------------------------------------------------

    async def _session_for(self, profile: str, fresh: bool = False) -> AsyncSession:
        if not fresh and self._session is not None and self._session_profile == profile:
            return self._session
        if self._session is not None:
            self._stale.append(self._session)
        proxy = await self._proxy_factory() if self._proxy_factory else None
        self._session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=REQUEST_TIMEOUT,
        )
        self._session.headers.update(DEFAULT_HEADERS)
        self._session_profile = profile
        return self._session

    async def close(self) -> None:
        for session in [*self._stale, self._session]:
            if session is None:
                continue
            try:
                await session.close()
            except Exception:  # noqa: BLE001 -- closing a dead session is not an error
                pass
        self._stale.clear()
        self._session = None

    # -- public ------------------------------------------------------------

    async def get_flight(self, url: str) -> str:
        """Flight stream of an App Router page (RSC first, HTML fallback)."""
        body, ctype = await self._get(url, RSC_HEADERS)
        if "text/x-component" in ctype:
            return body
        stream = stream_from_html(body)
        if not stream:
            # The RSC header was ignored AND the HTML has no stream: ask again
            # for plain HTML before concluding the page changed shape.
            body, _ = await self._get(url, HTML_HEADERS)
            stream = stream_from_html(body)
        return stream

    async def get_html(self, url: str) -> str:
        body, _ = await self._get(url, HTML_HEADERS)
        return body

    @property
    def winning_profile(self) -> str:
        return self._winner

    # -- ladder --------------------------------------------------------------

    async def _get(self, url: str, headers: dict) -> tuple[str, str]:
        failures: list[str] = []
        for rnd in range(LADDER_ROUNDS):
            order = [self._winner] + [p for p in self._ladder if p != self._winner]
            for profile in order:
                try:
                    result = await self._attempt(profile, url, headers)
                except NotFound:
                    raise
                except Blocked as exc:
                    failures.append(f"r{rnd + 1} {profile}: {exc}")
                    continue
                if profile != self._winner:
                    log.info(f"TLS {self._winner!r} refused, {profile!r} answered -- remembering it")
                    self._winner = profile
                return result
            if rnd + 1 < LADDER_ROUNDS:
                delay = _backoff(rnd, LADDER_ROUND_DELAY)
                log.warning(f"whole TLS ladder refused for {url}; retrying in {delay:.0f}s on fresh IPs")
                await asyncio.sleep(delay)
        raise Blocked(f"all TLS profiles refused across {LADDER_ROUNDS} rounds: {'; '.join(failures[-4:])}")

    async def _attempt(self, profile: str, url: str, headers: dict) -> tuple[str, str]:
        """One profile. A challenge and a timeout are different failures: a
        timeout says "again", a challenge says "not this fingerprint from this
        IP" -- so a challenge gets a fresh session (new exit IP) and, after
        CHALLENGE_RETRIES, hands the URL to the next rung."""
        last: Exception | None = None
        challenged = 0
        for attempt in range(MAX_RETRIES):
            session = await self._session_for(profile, fresh=attempt > 0 and challenged > 0)
            try:
                self.requests += 1
                r = await session.get(url, headers=headers, allow_redirects=True)
            except Exception as exc:  # noqa: BLE001 -- network errors are retryable
                last = exc
                # A dead proxy session is as likely as a slow server.
                await self._session_for(profile, fresh=True)
                await asyncio.sleep(_backoff(attempt))
                continue

            raw = r.content or b""
            self.bytes += len(raw)
            if r.status_code == 404:
                raise NotFound(f"404 for {url}")
            if r.status_code == 403 or any(m in raw[:4096] for m in BLOCK_MARKERS):
                self.challenges += 1
                challenged += 1
                last = Blocked(f"Cloudflare challenge ({r.status_code}, {len(raw)} B)")
                if challenged >= CHALLENGE_RETRIES:
                    raise last
                await asyncio.sleep(_backoff(0))
                continue
            if r.status_code in (429, 500, 502, 503, 504, 520, 522, 524):
                last = Blocked(f"HTTP {r.status_code}")
                await asyncio.sleep(_backoff(attempt + (2 if r.status_code == 429 else 0)))
                continue
            if r.status_code >= 400:
                raise NotFound(f"HTTP {r.status_code} for {url}")
            return r.text, (r.headers.get("content-type") or "").lower()
        raise Blocked(f"{MAX_RETRIES} attempts on {profile}: {last!r}")
