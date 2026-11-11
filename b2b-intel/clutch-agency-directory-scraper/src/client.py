"""HTTP transport for clutch.co.

One host, one gate: Cloudflare, answering on the TLS fingerprint. Three of the
six profiles on the recon ladder are challenged outright, so the client keeps a
ladder and remembers which profile won rather than pinning one and failing a run
it should have survived (the lesson Google Hotels cost the portfolio).

A challenge is detected by body marker, not only by status code: Cloudflare's
interstitial arrives as HTTP 403 with ``Just a moment...`` in the first few
hundred bytes, and the same page can arrive with a 200 when the challenge is
served as a soft redirect.

Requests are made inside one ``Session`` so the ``cf_clearance``-style cookies
Cloudflare hands out on the first successful request are reused. During recon,
eight consecutive requests in one session all returned 200 while a cold session
occasionally drew a 403 on its first request -- so a retry on a fresh session is
worth more than a longer sleep.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    CHALLENGE_DELAY,
    CHALLENGE_RETRIES,
    DEFAULT_HEADERS,
    LADDER_ROUND_DELAY,
    LADDER_ROUNDS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
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
    """Challenged by Cloudflare, or unusable after the whole TLS ladder."""


class NotFound(Exception):
    """404 -- no such category, profile or sitemap shard."""


class ClutchClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None,
                 proxy_factory=None):
        self._proxy_url = proxy_url
        # Returns a fresh proxy URL (a new exit IP). Cloudflare's verdict here is
        # partly per IP, so a retry on a new session also takes a new address.
        self._proxy_factory = proxy_factory
        self._ladder = list(TLS_LADDER)
        if profile and profile not in self._ladder:
            self._ladder = [profile, *self._ladder]
        elif profile:
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]
        self._session: AsyncSession | None = None
        self._session_profile: str | None = None
        self._stale: list[AsyncSession] = []
        self.requests = 0
        self.challenges = 0

    # -- session -----------------------------------------------------------

    def _session_for(self, profile: str, fresh: bool = False) -> AsyncSession:
        if not fresh and self._session is not None and self._session_profile == profile:
            return self._session
        if self._session is not None:
            self._stale.append(self._session)
            if self._proxy_factory is not None:
                self._proxy_url = self._proxy_factory()
        self._session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=REQUEST_TIMEOUT,
        )
        self._session.headers.update(DEFAULT_HEADERS)
        self._session_profile = profile
        return self._session

    async def close(self) -> None:
        """``AsyncSession.close`` is a coroutine; not awaiting it leaves the
        connection pool open and raises a RuntimeWarning at interpreter exit."""
        for session in [*self._stale, self._session]:
            if session is None:
                continue
            try:
                await session.close()
            except Exception:  # noqa: BLE001 -- closing a dead session is not an error
                pass
        self._stale.clear()
        self._session = None
        self._session_profile = None

    # -- fetching ----------------------------------------------------------

    async def get_text(self, url: str, allow_404: bool = False) -> str:
        """Fetch one document, walking the TLS ladder -- twice.

        Two facts measured on this source pull in opposite directions, and the
        policy has to satisfy both:

        * **Which profile passes depends on the IP.** chrome124 leads from a
          residential line and is refused outright from Apify's datacenter
          ranges. So the ladder must be walked, and walked cheaply -- three
          rejections of a profile that is simply wrong here are three wasted
          requests.
        * **A refusal is often transient.** A run on 0.0.1 was refused 8 times in
          10 requests and still finished, because it kept trying. A run on 0.0.2
          with a single tight pass gave up after 6 and failed outright.

        Hence two passes. The first is quick: each profile gets a couple of
        attempts, so the right one is found in seconds. If the whole ladder is
        refused, that is treated as a moment rather than a verdict -- the run
        waits and walks the ladder again with a longer delay before it gives up.
        """
        failures: list[str] = []

        for attempt_round in range(LADDER_ROUNDS):
            order = [self._winner] + [p for p in self._ladder if p != self._winner]
            for profile in order:
                try:
                    body = await self._attempt(profile, url, allow_404)
                except NotFound:
                    raise
                except Blocked as exc:
                    failures.append(f"round {attempt_round + 1} {profile}: {exc}")
                    continue
                else:
                    if profile != self._winner:
                        log.info(f"TLS {self._winner!r} was refused, {profile!r} answered -- remembering it")
                        self._winner = profile
                    return body
            if attempt_round + 1 < LADDER_ROUNDS:
                delay = LADDER_ROUND_DELAY * (2**attempt_round)
                log.info(f"whole ladder refused for {url}; waiting {delay:.0f}s and trying again")
                await asyncio.sleep(delay)

        raise Blocked(
            f"every TLS profile was refused across {LADDER_ROUNDS} rounds for {url} -- "
            f"{'; '.join(failures[-6:])}"
        )

    async def _attempt(self, profile: str, url: str, allow_404: bool) -> str:
        """One profile, with two different retry budgets.

        A challenge and a timeout are not the same failure. A timeout says "try
        again"; a challenge says "this fingerprint is wrong **from this IP**",
        and retrying it three times with exponential backoff is the expensive way
        to learn what the next profile answers in one request. Measured on the
        platform: chrome124 leads locally but is challenged outright from Apify's
        datacenter IPs, and the old policy spent ~35s and 8 challenges per run
        rediscovering that on every cold session.
        """
        last: Exception | None = None
        challenged = 0
        for attempt in range(MAX_RETRIES):
            # A challenge is usually specific to the session that drew it, so a
            # retry uses a fresh session rather than the cookie jar that failed.
            session = self._session_for(profile, fresh=attempt > 0)
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
                    return ""
                raise NotFound(f"404 for {url}")

            is_challenge = any(m in raw[:2048] for m in BLOCK_MARKERS) or r.status_code == 403
            if is_challenge:
                self.challenges += 1
                challenged += 1
                last = Blocked(f"Cloudflare challenge ({r.status_code}, {len(raw)} bytes)")
                if challenged >= CHALLENGE_RETRIES:
                    # Hand the URL to the next profile instead of paying for a
                    # third rejection of one that has now failed twice.
                    raise last
                await asyncio.sleep(CHALLENGE_DELAY)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = Blocked(f"HTTP {r.status_code}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if r.status_code >= 400:
                raise NotFound(f"HTTP {r.status_code} for {url}")
            return r.text

        raise Blocked(f"exhausted {MAX_RETRIES} attempts on {profile}: {last!r}")

    async def probe(self, url: str, profile: str) -> dict:
        """One raw request on one named profile -- used by the reference mode to
        re-test the TLS matrix rather than trusting what recon wrote down."""
        session = self._session_for(profile, fresh=True)
        try:
            self.requests += 1
            r = await session.request("GET", url, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001 -- a dead profile is a result, not a crash
            return {"profile": profile, "status": None, "bytes": 0, "error": f"{type(exc).__name__}: {exc}"[:200]}
        raw = r.content or b""
        challenged = any(m in raw[:2048] for m in BLOCK_MARKERS)
        return {
            "profile": profile,
            "status": r.status_code,
            "bytes": len(raw),
            "challenged": challenged,
            "error": None,
        }

    @property
    def winning_profile(self) -> str:
        return self._winner
