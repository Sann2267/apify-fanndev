"""One HTTP client for every LinkedIn actor in this portfolio.

Two surfaces live behind the same host and they behave nothing alike:

*Guest surface* -- ``/jobs-guest/...``, ``/in/{slug}``, ``/company/{slug}``,
``/posts/...``, ``/pulse/...``, ``/embed/feed/...``. No cookie, no WAF, and no
TLS gate: a sweep of chrome133a/chrome120/safari18_0/firefox135/edge101 all
returned 200 on the same company page. What it *does* have is a rate gate that
answers HTTP 999 with a 1,530-byte stub. The gate is per-IP and per-burst, not
per-URL: three back-to-back requests tripped it, and the same URLs answered 200
again after a four-second pause. That is the whole reason this client sleeps
between requests rather than hammering and retrying.

*Voyager surface* -- ``/voyager/api/...``. Answers 403 to anonymous callers and
needs the buyer's own ``li_at`` session cookie plus a ``csrf-token`` header that
matches the ``JSESSIONID`` cookie. LinkedIn accepts a client-chosen JSESSIONID
as long as the two agree, which is what ``_session_id`` builds.

Deliberately absent: any username/password login. A buyer pastes a cookie they
already hold; this code never authenticates on their behalf and never stores the
cookie anywhere but the live request.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from curl_cffi import requests

# Verified 2026-09-20: all five answer 200 on the guest surface, so rotating
# between them costs nothing and avoids one fingerprint carrying a whole run.
TLS_PROFILES = ["chrome133a", "chrome120", "safari18_0", "firefox135", "edge101"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
]

BASE = "https://www.linkedin.com"

# The rate gate announces itself as HTTP 999 with a ~1.5 KB stub that reads
# LinkedIn's trkCode cookie and bounces to the auth wall.
#
# Body size alone is NOT a usable signal for it, which is worth stating because
# the obvious heuristic is wrong: the guest jobs endpoint answers 200 with a
# 26-byte body once pagination runs past the last result. Treating that as the
# gate would send a run into pointless exponential backoff at the end of every
# search. So the gate is keyed on the 999 status, or on the stub's own markers
# appearing in a 200.
GATE_MARKERS = ("trkCode=", "trkInfo=")


class LinkedInError(RuntimeError):
    """Any non-recoverable failure against LinkedIn."""


class RateGated(LinkedInError):
    """HTTP 999 / stub response -- the per-IP burst gate, cleared by waiting."""


class AuthRequired(LinkedInError):
    """The surface needs a li_at cookie, or the supplied one is no longer valid."""


class NotFound(LinkedInError):
    """Slug, id or URL does not resolve."""


def _session_id() -> str:
    """A JSESSIONID value; the csrf-token header must repeat it exactly."""
    return "ajax:" + "".join(random.choices("0123456789", k=19))


class LinkedInClient:
    """Guest-surface reader, with an optional authenticated Voyager path."""

    def __init__(
        self,
        log: Any,
        *,
        li_at: str | None = None,
        proxy_url: str | None = None,
        min_delay: float = 2.0,
        max_delay: float = 8.0,
        max_retries: int = 3,
        timeout: int = 45,
    ) -> None:
        self.log = log
        self.li_at = (li_at or "").strip() or None
        self.proxy_url = proxy_url
        self.min_delay = max(0.0, float(min_delay))
        self.max_delay = max(self.min_delay, float(max_delay))
        self.max_retries = max(1, int(max_retries))
        self.timeout = timeout
        self._jsession = _session_id()
        self._user_agent = random.choice(USER_AGENTS)
        self._requests = 0
        self._gate_hits = 0
        self._first = True

    # -- bookkeeping the actors surface in their run log ------------------

    @property
    def authenticated(self) -> bool:
        return self.li_at is not None

    @property
    def stats(self) -> dict:
        return {"requests": self._requests, "rateGateHits": self._gate_hits}

    # -- request plumbing --------------------------------------------------

    def _cookies(self) -> dict:
        if not self.li_at:
            return {}
        return {"li_at": self.li_at, "JSESSIONID": f'"{self._jsession}"'}

    def _headers(self, voyager: bool) -> dict:
        headers = {
            "User-Agent": self._user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }
        if voyager:
            headers.update(
                {
                    "accept": "application/vnd.linkedin.normalized+json+2.1",
                    "csrf-token": self._jsession,
                    "x-restli-protocol-version": "2.0.0",
                    "x-li-lang": "en_US",
                    "referer": f"{BASE}/feed/",
                }
            )
        else:
            headers["Accept"] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            )
        return headers

    async def _pause(self) -> None:
        """Human-like gap between page loads. The first request does not wait."""
        if self._first:
            self._first = False
            return
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

    async def fetch(
        self,
        url: str,
        *,
        voyager: bool = False,
        allow_redirects: bool = True,
    ) -> str:
        """GET a URL, honouring the delay budget and retrying past the 999 gate."""
        if voyager and not self.li_at:
            raise AuthRequired(
                "This endpoint is only reachable with a li_at session cookie."
            )
        last: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            await self._pause()
            try:
                response = requests.get(
                    url,
                    impersonate=random.choice(TLS_PROFILES),
                    headers=self._headers(voyager),
                    cookies=self._cookies(),
                    proxies=(
                        {"http": self.proxy_url, "https": self.proxy_url}
                        if self.proxy_url
                        else None
                    ),
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except Exception as exc:  # transport failure -- worth one more try
                last = exc
                self.log.warning(
                    f"Request failed ({type(exc).__name__}) on attempt "
                    f"{attempt}/{self.max_retries}: {str(exc)[:120]}"
                )
                continue

            self._requests += 1
            body = response.text or ""
            status = response.status_code

            gated = status == 999 or (
                len(body) < 4000 and all(marker in body for marker in GATE_MARKERS)
            )
            if gated:
                self._gate_hits += 1
                last = RateGated(f"HTTP {status} rate gate on {url}")
                backoff = min(60.0, self.max_delay * (2**attempt))
                self.log.warning(
                    f"LinkedIn rate gate hit (attempt {attempt}/{self.max_retries}) "
                    f"-- backing off {backoff:.0f}s. Raising the delay range or "
                    "enabling a residential proxy makes this rarer."
                )
                await asyncio.sleep(backoff)
                continue

            if status in (401, 403):
                raise AuthRequired(
                    f"LinkedIn answered {status}. The li_at cookie is missing, "
                    "expired or was invalidated by LinkedIn -- paste a fresh one."
                )
            if status == 404:
                raise NotFound(f"LinkedIn has no page at {url}")
            if status >= 400:
                last = LinkedInError(f"HTTP {status} on {url}")
                continue

            # A guest page that bounced to the login wall carries no data.
            if "/uas/login" in str(response.url) or "/authwall" in str(response.url):
                raise AuthRequired(
                    f"{url} is behind LinkedIn's login wall for anonymous "
                    "visitors. Supply a li_at cookie to read it."
                )
            return body

        if isinstance(last, LinkedInError):
            raise last
        raise LinkedInError(f"Giving up on {url}: {last}")

    async def voyager(self, path: str, params: str = "") -> dict:
        """Call a Voyager endpoint and return its decoded JSON body."""
        url = f"{BASE}/voyager/api/{path.lstrip('/')}"
        if params:
            url = f"{url}?{params}"
        body = await self.fetch(url, voyager=True)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LinkedInError(
                f"Voyager returned a non-JSON body for {path} "
                f"({len(body)} bytes) -- LinkedIn likely changed the endpoint."
            ) from exc

    async def graphql(self, query_id: str, variables: str) -> dict:
        """Voyager GraphQL, whose variables use LinkedIn's own bracket syntax."""
        return await self.voyager(
            "graphql", f"variables={variables}&queryId={query_id}"
        )


# -- proxy wiring ---------------------------------------------------------


async def proxy_url_from(
    actor: Any, actor_input: dict, *, required_reason: str | None = None
) -> str | None:
    """Build a proxy URL from the buyer's proxy input.

    ``required_reason`` is set by the actors that drive an authenticated
    session: LinkedIn scores a datacenter exit IP against the account's usual
    location, so running a buyer's own cookie through one is how sessions get
    flagged. Those actors warn loudly rather than silently proceeding.
    """
    configuration_input = actor_input.get("proxyConfiguration") or {}
    if not configuration_input.get("useApifyProxy"):
        if required_reason:
            actor.log.warning(required_reason)
        return None
    groups = configuration_input.get("apifyProxyGroups") or None
    country = configuration_input.get("apifyProxyCountry") or None
    try:
        configuration = await actor.create_proxy_configuration(
            groups=groups, country_code=country
        )
    except Exception as exc:  # never end a run over proxy misconfiguration
        actor.log.warning(f"Proxy configuration failed ({exc}) -- continuing direct.")
        return None
    if configuration is None:
        actor.log.warning(
            "Proxy was requested but is not available on this account -- "
            "continuing direct."
        )
        return None
    if groups and "RESIDENTIAL" not in groups:
        actor.log.warning(
            f"Proxy group {groups} is not RESIDENTIAL. LinkedIn treats datacenter "
            "exit IPs as suspicious, which is what gets a session cookie flagged."
        )
    return await configuration.new_url()
