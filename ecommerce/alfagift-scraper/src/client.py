"""HTTP client for the Alfagift gateway: typed outcomes, retries, pacing.

Alfagift is one of the calmer targets in this portfolio -- no WAF, no TLS gate,
no rate limiting reached during recon (see `constants.py`). So this client is
deliberately plain. What it does have to get right is telling four different
server answers apart, because Alfagift signals all four with statuses that mean
something different here than they do elsewhere:

  401 + {"code":"401"}       the fingerprint header is missing or no longer
                             decrypts. NOT a login problem and NOT rate
                             limiting. Retrying cannot fix it, so it raises
                             immediately saying what to re-harvest.
  404 + "Product not found"  a genuine dead id. Final answer.
  500 + "solr.brands.error"  a permanent upstream index fault on five brand
                             letters. Looks transient, never is -- see
                             BRAND_LETTERS_UPSTREAM_BROKEN.
  500 + "For input string"   the id was the wrong TYPE (a SKU where a numeric
                             productId belongs). A caller error, not a server
                             one.

Everything else in the 5xx range is treated as genuinely transient and retried
with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    API_ROOT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    SITE_ROOT,
    TLS_PROFILES,
)
from .gate import new_fingerprint, new_trx_id

log = logging.getLogger("alfagift.client")

RETRY_STATUS = (408, 425, 502, 503, 504)

# A 429 would mean the app's /too-many-request redirect threshold was crossed.
# Recon never reached it, so this is precautionary: sit still rather than
# rotate, because a volume limit is not fingerprint-shaped.
RATE_LIMIT_COOLDOWN_SECS = 30.0


class AlfagiftError(Exception):
    """Base for the outcomes callers route on."""


class AlfagiftGateRejected(AlfagiftError):
    """HTTP 401 from the gateway -- the fingerprint header was not accepted.

    Raised, never retried. If this fires, Alfagift has rotated the AES
    passphrase or IV baked into `constants.py`; the fix is to re-harvest them
    from the live bundle, not to try again.
    """


class AlfagiftNotFound(AlfagiftError):
    """The gateway answered definitively that the entity does not exist."""


class AlfagiftBadInput(AlfagiftError):
    """The identifier was the wrong shape for this endpoint.

    Alfagift reports this as HTTP 500 "For input string: <value>", a Java parse
    failure leaking through. It means a non-numeric value was sent where a
    numeric productId or brandId belongs -- typically a SKU.
    """


class AlfagiftUpstreamBroken(AlfagiftError):
    """A permanent server-side fault that retrying will not clear."""


class AlfagiftBlocked(AlfagiftError):
    """Transport failure or a status that survived the whole retry ladder."""


class AlfagiftClient:
    """One client per run, holding the run's gate token and a curl_cffi session.

    The fingerprint is minted once and reused for the whole run: the gateway
    does not bind it to a session, expire it, or count against it, so
    re-minting per request would only burn CPU.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
        request_delay: float = DEFAULT_REQUEST_DELAY_SECS,
    ) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self.fingerprint = new_fingerprint()
        self._profile_idx = 0
        self._session: cr.Session | None = None
        self._lock = asyncio.Lock()
        self._last_at = 0.0
        self.request_count = 0
        self.retry_count = 0

    # -- session plumbing --------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    def _session_or_new(self) -> cr.Session:
        if self._session is None:
            kwargs: dict[str, Any] = {
                "impersonate": self.profile,
                "timeout": self.request_timeout,
            }
            if self.proxy_url:
                kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
            self._session = cr.Session(**kwargs)
        return self._session

    def rotate_profile(self) -> str:
        """Only ever called after a transport error.

        Alfagift does not fingerprint TLS, so this buys a fresh connection
        rather than a fresh identity.
        """
        self._profile_idx += 1
        self.close()
        log.info("Rotated TLS profile to %s after a transport error", self.profile)
        return self.profile

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
            self._session = None

    # -- headers -----------------------------------------------------------

    def headers(self, latitude: float = 0.0, longitude: float = 0.0) -> dict[str, str]:
        """Exactly the header set the web app sends, and exactly the set the
        CORS preflight allows. `authorization` is omitted because everything
        this actor reads is anonymous.
        """
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id",
            "Origin": SITE_ROOT,
            "Referer": SITE_ROOT + "/",
            "deviceType": "Web",
            "deviceModel": "Chrome",
            "latitude": str(latitude),
            "longitude": str(longitude),
            "trxId": new_trx_id(),
            "fingerprint": self.fingerprint,
        }

    # -- pacing ------------------------------------------------------------

    async def _pace(self) -> None:
        if self.request_delay <= 0:
            return
        async with self._lock:
            gap = time.monotonic() - self._last_at
            if gap < self.request_delay:
                await asyncio.sleep(self.request_delay - gap)
            self._last_at = time.monotonic()

    # -- core --------------------------------------------------------------

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> Any:
        """GET a gateway endpoint and decode its JSON."""
        url = API_ROOT.rstrip("/") + "/" + path.lstrip("/")
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

        resp = await self._request(url, latitude=latitude, longitude=longitude)
        body = resp.text or ""
        if not body.strip():
            # A 200 with a zero-length body is how the promotion-products
            # endpoint answers an id that is a BANNER id rather than a
            # PROMOTION id. Callers must tell that apart from "campaign empty".
            return None
        try:
            return json.loads(body)
        except ValueError as exc:
            raise AlfagiftBlocked(
                f"{url} answered HTTP {resp.status_code} with non-JSON "
                f"({len(body)} bytes)"
            ) from exc

    async def _request(self, url: str, *, latitude: float, longitude: float) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            if attempt:
                self.retry_count += 1
                delay = min(2**attempt + random.uniform(0, 1.0), 20)
                log.info(
                    "Retry %d/%d for %s in %.1fs",
                    attempt, self.max_retries - 1, url, delay,
                )
                await asyncio.sleep(delay)

            await self._pace()
            session = self._session_or_new()
            self.request_count += 1
            try:
                resp = await asyncio.to_thread(
                    session.get, url, headers=self.headers(latitude, longitude)
                )
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", url, exc)
                self.rotate_profile()
                continue

            if resp.status_code == 200:
                return resp

            if resp.status_code == 401:
                raise AlfagiftGateRejected(
                    "The gateway rejected the fingerprint header. This is not a "
                    "login and not a rate limit -- Alfagift has almost "
                    "certainly rotated the AES passphrase/IV that "
                    "src/constants.py pins. Re-harvest them from the live "
                    "https://alfagift.id/_nuxt/ bundle (grep for 'm4p1-' or "
                    "'passphrase') and update GATE_PASSPHRASE / GATE_IV."
                )

            if resp.status_code == 404:
                raise AlfagiftNotFound(f"HTTP 404 on {url}: {_message(resp)}")

            if resp.status_code == 429:
                last_error = AlfagiftBlocked(f"HTTP 429 on {url}")
                log.warning(
                    "Rate limited on %s. Pausing %.0fs; raise requestDelaySecs "
                    "if this repeats.", url, RATE_LIMIT_COOLDOWN_SECS,
                )
                await asyncio.sleep(RATE_LIMIT_COOLDOWN_SECS)
                continue

            if resp.status_code == 500:
                detail = _message(resp)
                if "solr.brands.error" in detail:
                    raise AlfagiftUpstreamBroken(
                        f"{url}: Alfagift's brand index is broken for this "
                        f"letter and answers 500 on every attempt"
                    )
                if "For input string" in detail:
                    raise AlfagiftBadInput(f"{url}: {detail}")
                last_error = AlfagiftBlocked(f"HTTP 500 on {url}: {detail}")
                log.warning("HTTP 500 on %s: %s", url, detail)
                continue

            if resp.status_code in RETRY_STATUS:
                last_error = AlfagiftBlocked(f"HTTP {resp.status_code} on {url}")
                log.warning("HTTP %s on %s", resp.status_code, url)
                continue

            raise AlfagiftBlocked(
                f"HTTP {resp.status_code} on {url}: {(resp.text or '')[:200]}"
            )

        raise AlfagiftBlocked(
            f"{url} failed after {self.max_retries} attempts"
        ) from last_error


def _message(resp: Any) -> str:
    """Pull the human-readable part out of one of the gateway's error bodies.

    Alfagift uses two different error envelopes -- the Spring one
    ({statusCode, message, errors[]}) and the app one ({code, message}) -- so
    this reads whichever is present and falls back to the raw body.
    """
    try:
        parsed = json.loads(resp.text or "")
    except ValueError:
        return (resp.text or "")[:200]
    if not isinstance(parsed, dict):
        return (resp.text or "")[:200]
    parts = [str(parsed.get("message") or "")]
    errors = parsed.get("errors")
    if isinstance(errors, list):
        parts.extend(str(e) for e in errors)
    return " | ".join(p for p in parts if p)[:300]
