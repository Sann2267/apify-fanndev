"""HTTP transport for Shopee's flash-sale API.

Shopee gates most of its API at the load balancer and returns an identical
`{"error":90309999,...}` body with HTTP 403 regardless of TLS profile -- 19
profiles were tried across 8 country domains during earlier recon, all 403, and
no `Set-Cookie` is ever issued so there is no session to warm up.

That makes the client's job unusual: a 403 here is **not** a transient failure
worth retrying through a ladder, it is a structural answer. So `get_json`
distinguishes the two:

* :class:`Gated` -- Shopee's load-balancer refusal. Reported once, immediately,
  with the endpoint named. Retrying is pointless and only burns compute.
* :class:`Blocked` -- an ordinary transport failure, which does go through the
  TLS ladder.

The flash-sale endpoints this Actor uses answered 200 on every profile and
every regional domain tested.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    ACCEPT_LANGUAGE,
    BASE_HEADERS,
    GATE_ERROR,
    MAX_ATTEMPTS,
    MIN_BYTES,
    RETRY_DELAY_BASE,
    TLS_LADDER,
)

log = logging.getLogger(__name__)


class Gated(Exception):
    """Shopee's anti-bot gate answered. Retrying will not help."""


class Blocked(Exception):
    """Transport failure after the whole TLS ladder."""


class NotFound(Exception):
    """No such session, shop or item."""


class ShopeeClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None):
        self._proxy_url = proxy_url
        self._ladder = list(TLS_LADDER)
        if profile:
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]
        self.attempts_used = 0

    def _new_session(self, profile: str, domain: str, country: str) -> AsyncSession:
        session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=60,
        )
        session.headers.update({
            **BASE_HEADERS,
            "Accept-Language": ACCEPT_LANGUAGE.get(country, "en-US,en;q=0.9"),
            "Referer": f"https://{domain}/",
        })
        return session

    async def get_json(self, url: str, domain: str, country: str) -> tuple[dict, str, int]:
        """Return ``(payload, winning_tls_profile, attempts)``."""
        order = [self._winner] + [p for p in self._ladder if p != self._winner]
        last_error = "no attempt made"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            profile = order[(attempt - 1) % len(order)]
            session = self._new_session(profile, domain, country)
            try:
                response = await session.get(url)
                body = response.text or ""

                if response.status_code == 404:
                    raise NotFound(url)

                payload = None
                try:
                    payload = response.json()
                except Exception:
                    payload = None

                # The gate answers 403 with a stable error code. Fail fast.
                if isinstance(payload, dict) and payload.get("error") == GATE_ERROR:
                    raise Gated(
                        f"Shopee anti-bot gate on {url.split('?')[0]} "
                        f"(HTTP {response.status_code}, error {GATE_ERROR})"
                    )
                if response.status_code == 403:
                    raise Gated(f"HTTP 403 on {url.split('?')[0]}")

                # A parsed dict is an answer, however short. Gating on length
                # too would turn Shopee's short error bodies (a 48-byte
                # `{"error":…}` reply) into four pointless retries and then a
                # transport error, hiding what the API actually said.
                if isinstance(payload, dict):
                    self._winner = profile
                    self.attempts_used = attempt
                    return payload, profile, attempt

                if payload is not None and len(body) >= MIN_BYTES:
                    self._winner = profile
                    self.attempts_used = attempt
                    return payload, profile, attempt

                last_error = f"HTTP {response.status_code}, {len(body)}B, unparseable"
            except (Gated, NotFound):
                raise
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.debug("%s on %s: %s", url, profile, last_error)
            finally:
                await session.close()

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_BASE * attempt)

        self.attempts_used = MAX_ATTEMPTS
        raise Blocked(f"{url}: {MAX_ATTEMPTS} attempts, last: {last_error}")
