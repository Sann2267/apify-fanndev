"""HTTP transport for the two ESPN API hosts.

No WAF answered during recon -- every request in this Actor reached 200 over
plain HTTP with no cookie and no key. The TLS ladder is here anyway because of
the lesson the portfolio paid for on Google Hotels: the profile that wins on a
local residential IP is not the profile that wins from Apify's proxy pool, and
an Actor that pins one profile fails a run it should have survived. ``chrome124``
leads because it answered every recon request; ``chrome131`` is deliberately
absent, being widely blocklisted in 2026 (`.ai/CLAUDE.md` rule 2).

The client also owns the `$ref` cache. ESPN's core API is HATEOAS -- lists hand
back pointers -- so the same athlete or team pointer is followed dozens of times
in one run unless something remembers it. 659 NFL player props resolve from 47
distinct athletes; the cache turns a 659-request job into a 47-request one.
"""

import asyncio
import json
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    DEFAULT_REF_BUDGET,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_LADDER,
)

log = logging.getLogger(__name__)

BLOCK_MARKERS = (b"Just a moment", b"challenge-platform", b"cf-mitigated", b"Access denied")


class Blocked(Exception):
    """Challenged, or unusable after the whole TLS ladder."""


class NotFound(Exception):
    """404 -- no such league, event, season or provider."""


def normalize_ref(ref: str | None) -> str | None:
    """Make an ESPN ``$ref`` fetchable.

    Two rewrites, both mandatory. ESPN writes pointers with the ``http://``
    scheme, and the ones inside SITE's ``summary`` response name the internal
    host ``sports.core.api.espn.pvt``, which resolves nowhere: 436 of 436
    pointers in that one response were ``.pvt``. Following them verbatim fails
    every time.
    """
    if not ref:
        return None
    return ref.replace("sports.core.api.espn.pvt", "sports.core.api.espn.com").replace(
        "http://", "https://", 1
    )


class EspnClient:
    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str | None = None,
        ref_budget: int = DEFAULT_REF_BUDGET,
    ):
        self._proxy_url = proxy_url
        self._ladder = list(TLS_LADDER)
        if profile:
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]
        self._session: AsyncSession | None = None
        self._stale: list[AsyncSession] = []
        self._session_profile: str | None = None
        self._ref_cache: dict[str, dict] = {}
        self._ref_budget = ref_budget
        self.ref_lookups = 0
        self.ref_cache_hits = 0
        self.requests = 0

    # -- session -----------------------------------------------------------

    def _session_for(self, profile: str) -> AsyncSession:
        if self._session is not None and self._session_profile == profile:
            return self._session
        if self._session is not None:
            self._stale.append(self._session)
        self._session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=60,
        )
        self._session.headers.update(DEFAULT_HEADERS)
        self._session_profile = profile
        return self._session

    async def close(self) -> None:
        """``AsyncSession.close`` is a coroutine -- calling it without awaiting
        leaves the connection pool open and raises a RuntimeWarning at exit."""
        for session in [*self._stale, self._session]:
            if session is None:
                continue
            try:
                await session.close()
            except Exception:  # noqa: BLE001 -- closing a dead session is not an error
                pass
        self._stale.clear()
        self._session = None

    # -- fetching ----------------------------------------------------------

    async def get_json(self, url: str, allow_404: bool = False) -> dict:
        """Fetch one JSON document, walking the TLS ladder if a profile is blocked."""
        order = [self._winner] + [p for p in self._ladder if p != self._winner]
        failures: list[str] = []

        for profile in order:
            try:
                payload = await self._attempt(self._session_for(profile), url, allow_404)
            except NotFound:
                raise
            except Blocked as exc:
                failures.append(f"{profile}: {exc}")
                continue
            else:
                if profile != self._winner:
                    log.info(f"TLS {self._winner!r} blocked, {profile!r} won -- remembering it")
                    self._winner = profile
                return payload

        raise Blocked(f"every TLS profile was blocked for {url} -- {'; '.join(failures)}")

    async def _attempt(self, session: AsyncSession, url: str, allow_404: bool) -> dict:
        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                self.requests += 1
                r = await session.request("GET", url, allow_redirects=True)
            except Exception as exc:  # noqa: BLE001 -- network errors are retryable
                last = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            raw = r.content or b""
            if r.status_code == 404:
                if allow_404:
                    return {}
                raise NotFound(f"404 for {url}")
            if any(m in raw[:4096] for m in BLOCK_MARKERS):
                raise Blocked(f"challenge page ({r.status_code})")
            if r.status_code == 403:
                raise Blocked("403")
            if r.status_code in (429, 500, 502, 503, 504):
                last = Blocked(f"HTTP {r.status_code}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if r.status_code >= 400:
                # 400 is ESPN's answer to a malformed query (a date range sent
                # to the SITE host, an unknown league). Retrying will not help.
                raise NotFound(f"HTTP {r.status_code} for {url}: {raw[:200].decode('utf-8', 'replace')}")
            try:
                return json.loads(raw.decode("utf-8", "replace"))
            except ValueError as exc:
                raise Blocked(f"200 but not JSON ({len(raw)} bytes): {exc}") from exc

        raise Blocked(f"exhausted {MAX_RETRIES} retries: {last!r}")

    # -- $ref resolution ---------------------------------------------------

    async def resolve(self, ref: str | None) -> dict:
        """Follow a ``$ref``, cached, within the run's lookup budget.

        Returns ``{}`` when the pointer is missing, unfetchable or the budget is
        spent -- callers fall back to whatever id they already hold, so a record
        loses a name but is never dropped.
        """
        url = normalize_ref(ref)
        if not url:
            return {}
        key = url.split("?")[0]
        if key in self._ref_cache:
            self.ref_cache_hits += 1
            return self._ref_cache[key]
        if self.ref_lookups >= self._ref_budget:
            return {}
        self.ref_lookups += 1
        try:
            payload = await self.get_json(url)
        except Exception as exc:  # noqa: BLE001 -- a name is optional, the record is not
            log.debug(f"ref lookup failed for {url}: {exc!r}")
            payload = {}
        self._ref_cache[key] = payload
        return payload

    def seed_refs(self, entries: dict[str, dict]) -> None:
        """Pre-fill the cache (SITE ``/teams`` hands over a whole league at once)."""
        for key, value in entries.items():
            self._ref_cache.setdefault(key.split("?")[0], value)

    @property
    def winning_profile(self) -> str:
        return self._winner
