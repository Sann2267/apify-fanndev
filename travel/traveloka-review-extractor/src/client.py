"""Traveloka internal-API client shared by every actor in this family.

Three independent gates guard traveloka.com; only the second one is on our path:

1. **DataDome** sits on the HTML product pages (`/*/hotel*`, `/*/flight*`,
   `/*/activities*`) and answers 403 to every TLS profile, from residential
   Indonesian IPs included. We never fetch those pages -- every field below comes
   from the JSON API instead.
2. **A CloudFront cookie gate** answers `401 ... named cookie not present` to all
   of `/api/**`. Exactly one endpoint is allow-listed through it:
   `POST /api/v2/user/context/web` with `x-domain: user`. Its response mints the
   `tvl` / `tvs` / `tvo` cookies that open the rest of the API. HTML pages mint
   nothing, so "visit the homepage first" does not help.
3. **AWS WAF** guards the heavyweight search endpoints with
   `x-amzn-waf-action: captcha` -- not solvable headlessly. Those endpoints are
   deliberately absent from this client; see each actor's README for what that
   rules out.

`x-domain` is a gateway routing key, not a label: the same path resolves to a
different backend per domain, and a wrong value yields `Can not find API Domain`.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

from curl_cffi import requests

logger = logging.getLogger(__name__)

SITE = "https://www.traveloka.com"
API = SITE + "/api"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Every profile behaves identically against the API gate; we still rotate so a
# run does not present one fingerprint for hundreds of requests.
TLS_PROFILES = ("chrome131", "chrome124", "chrome120", "edge101", "safari17_0")

BOOTSTRAP_PATH = "/v2/user/context/web"
RETRY_STATUS = {429, 500, 502, 503, 504}


class TravelokaError(RuntimeError):
    """Raised when the API cannot be reached or answers with a hard failure."""


class GateError(TravelokaError):
    """Raised when a request is turned away by one of Traveloka's gates."""


class TravelokaClient:
    """Bootstraps a Traveloka session and issues internal JSON API calls."""

    def __init__(
        self,
        proxy_url: str | None = None,
        locale: str = "en-id",
        currency: str = "IDR",
        tls_profile: str | None = None,
        request_delay: float = 0.4,
        max_retries: int = 3,
        proxy_factory=None,
        bootstrap_attempts: int = 10,
    ) -> None:
        self.proxy_url = proxy_url
        # Called with no arguments to obtain a *fresh* proxy URL (a new exit IP).
        # Bootstrap is the one request AWS WAF sometimes challenges outright, and
        # the only cure is a different IP, so the client needs to be able to ask
        # for one rather than failing the whole run.
        self.proxy_factory = proxy_factory
        self.bootstrap_attempts = max(1, bootstrap_attempts)
        self.locale = locale
        self.currency = currency
        self.language = locale.split("-")[0]
        self.tls_profile = tls_profile or random.choice(TLS_PROFILES)
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._session: requests.Session | None = None
        self._booted_at = 0.0

    # -- session ---------------------------------------------------------

    def _new_session(self) -> requests.Session:
        session = requests.Session(
            impersonate=self.tls_profile,
            proxies=({"http": self.proxy_url, "https": self.proxy_url}
                     if self.proxy_url else None),
        )
        session.headers.update({
            "user-agent": UA,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": SITE,
            "accept-language": f"{self.language}-ID,{self.language};q=0.9",
        })
        return session

    def bootstrap(self) -> None:
        """Mint the `tvl`/`tvs`/`tvo` cookies that open `/api/**`.

        AWS WAF challenges this endpoint on some exit IPs -- not on the path, on
        the address. A challenged bootstrap answers 405 with a Human Verification
        page. When that happens we take a new proxy session (a new IP) and a new
        TLS profile and try again; a run only fails once every attempt is refused.
        """
        payload = {
            "clientInterface": "desktop",
            "data": {"client": "MOBILE_WEB", "info": {"User-Agent": UA}, "query": {}},
            "context": {},
            "fields": [],
        }
        last_error = ""
        for attempt in range(1, self.bootstrap_attempts + 1):
            if attempt > 1:
                self._rotate_identity()
            session = self._new_session()
            try:
                resp = session.post(
                    API + BOOTSTRAP_PATH, json=payload, timeout=45,
                    headers={"referer": f"{SITE}/{self.locale}/", "x-domain": "user",
                             "x-client-interface": "desktop"},
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"connection error: {exc}"
                logger.warning("Bootstrap attempt %d/%d: %s", attempt,
                               self.bootstrap_attempts, last_error)
                continue

            waf = resp.headers.get("x-amzn-waf-action")
            if waf or resp.status_code == 405:
                last_error = f"AWS WAF answered {waf or 'captcha'} on this exit IP"
                logger.warning("Bootstrap attempt %d/%d: %s; rotating identity.",
                               attempt, self.bootstrap_attempts, last_error)
                time.sleep(0.5 + random.random())
                continue
            if resp.status_code == 401:
                raise GateError(
                    "Session bootstrap was refused by the CloudFront cookie gate "
                    "(401 named cookie not present). Traveloka changed the "
                    "bootstrap contract; the actor needs updating."
                )
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}: {resp.text[:160]}"
                logger.warning("Bootstrap attempt %d/%d: %s", attempt,
                               self.bootstrap_attempts, last_error)
                continue

            self._session = session
            self._booted_at = time.time()
            logger.info("Traveloka session bootstrapped (TLS profile %s, attempt %d).",
                        self.tls_profile, attempt)
            return

        raise TravelokaError(
            f"Session bootstrap failed after {self.bootstrap_attempts} attempts "
            f"({last_error}). Enable or widen the proxy so the actor can reach "
            "Traveloka from an exit IP that AWS WAF does not challenge."
        )

    def _rotate_identity(self) -> None:
        """Swap to a different exit IP and TLS fingerprint."""
        if self.proxy_factory is not None:
            try:
                self.proxy_url = self.proxy_factory()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not obtain a new proxy session: %s", exc)
        remaining = [p for p in TLS_PROFILES if p != self.tls_profile]
        if remaining:
            self.tls_profile = random.choice(remaining)

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self.bootstrap()
        assert self._session is not None
        return self._session

    # -- calls -----------------------------------------------------------

    def call(self, path: str, domain: str, data: dict,
             referer_path: str = "", timeout: int = 90) -> dict:
        """POST one internal API call and return its `data` payload.

        Raises `GateError` when AWS WAF intercepts (status 202 `challenge` or
        405 `captcha`) so callers can report the gate instead of a parse error.
        """
        referer = f"{SITE}/{self.locale}/{referer_path.lstrip('/')}" if referer_path \
            else f"{SITE}/{self.locale}/"
        headers = {"referer": referer, "x-domain": domain,
                   "x-client-interface": "desktop"}
        body = {"fields": [], "clientInterface": "desktop", "data": data, "context": {}}

        last_error = ""
        waf_rotations = 0
        for attempt in range(1, self.max_retries + 1):
            if self.request_delay:
                time.sleep(self.request_delay)
            try:
                resp = self.session.post(API + path, json=body, timeout=timeout,
                                         headers=headers)
            except Exception as exc:  # noqa: BLE001
                last_error = f"connection error: {exc}"
                logger.warning("%s attempt %d/%d: %s", path, attempt,
                               self.max_retries, last_error)
                self._session = None
                continue

            waf = resp.headers.get("x-amzn-waf-action")
            if waf:
                # The review endpoints are not structurally gated; a WAF answer
                # here is about the exit IP, so a fresh IP usually clears it.
                if self.proxy_factory is not None and waf_rotations < 2:
                    waf_rotations += 1
                    logger.warning("%s: AWS WAF answered %s; rotating exit IP "
                                   "(%d/2).", path, waf, waf_rotations)
                    self._rotate_identity()
                    self._session = None
                    continue
                raise GateError(
                    f"{path} is guarded by AWS WAF (action={waf}). This endpoint "
                    "cannot be read without solving a visual CAPTCHA."
                )
            if resp.status_code == 401:
                # Session cookies expired mid-run; re-bootstrap once and retry.
                logger.info("Session expired on %s; re-bootstrapping.", path)
                self._session = None
                last_error = "session expired"
                continue
            if resp.status_code in RETRY_STATUS:
                last_error = f"HTTP {resp.status_code}"
                backoff = min(2 ** attempt, 12) + random.random()
                logger.warning("%s attempt %d/%d: %s, retrying in %.1fs",
                               path, attempt, self.max_retries, last_error, backoff)
                time.sleep(backoff)
                continue
            if resp.status_code != 200:
                raise TravelokaError(
                    f"{path} returned HTTP {resp.status_code}: {resp.text[:220]}")

            try:
                parsed = resp.json()
            except Exception as exc:  # noqa: BLE001
                raise TravelokaError(f"{path} returned non-JSON: {exc}") from exc

            if isinstance(parsed, dict) and parsed.get("errorMessage"):
                raise TravelokaError(f"{path}: {parsed['errorMessage'][:220]}")
            return (parsed or {}).get("data") or {}

        raise TravelokaError(f"{path} failed after {self.max_retries} attempts: {last_error}")

    async def call_async(self, path: str, domain: str, data: dict,
                         referer_path: str = "", timeout: int = 90) -> dict:
        """Run `call` off the event loop so the Actor stays responsive."""
        return await asyncio.to_thread(self.call, path, domain, data,
                                       referer_path, timeout)
