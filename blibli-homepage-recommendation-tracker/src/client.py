"""HTTP client for Blibli's internal JSON APIs.

Carries the Cloudflare bypass documented in `constants` -- TLS impersonation
plus a mandatory `Referer` -- and adds retry/backoff, TLS-profile rotation
and proxy-session rotation on block. Identical pattern to the other Blibli
actors in this portfolio; kept as a local copy (not a shared package) so
each actor stays independently deployable.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_HEADERS,
    MAX_RETRIES,
    ORIGIN,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

# Cloudflare serves its challenge/deny pages as HTML. Any of these in the
# body means we were gated regardless of the status code -- Blibli's deny
# response is a full ~248 KB storefront-looking HTML shell, not a tiny
# error, so status-only detection is not sufficient.
BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"__cf_chl",
    b"cf-error-details",
    b"Attention Required",
)


class BlockedError(Exception):
    """Every retry and every TLS profile was exhausted while still gated."""


class UpstreamShapeError(Exception):
    """A 200 response did not carry the JSON envelope this actor expects.

    Raised rather than returning `{}` so a Blibli-side schema change fails
    loudly instead of silently emptying the dataset.
    """


def _is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    body = response.content[:8192] if response.content else b""
    return any(marker in body for marker in BLOCK_MARKERS)


class BlibliClient:
    """Async JSON client with block-aware retries.

    `new_proxy_url` is Apify's `ProxyConfiguration.new_url`; calling it
    yields a fresh sticky residential session (usually a new egress IP),
    which is what actually clears a Cloudflare IP-reputation block -- a
    plain retry on the same IP tends to burn the whole budget.
    """

    def __init__(self, proxy_url: str | None = None, new_proxy_url=None):
        self._new_proxy_url = new_proxy_url
        self._profile_index = 0
        self._proxy_url = proxy_url
        self.session = self._build_session(proxy_url)

    @property
    def _profile(self) -> str:
        return TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]

    def _build_session(self, proxy_url: str | None) -> AsyncSession:
        return AsyncSession(
            impersonate=self._profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )

    async def _rotate(self) -> None:
        """Advance the TLS profile and, when possible, the egress IP."""
        self._profile_index += 1
        if self._new_proxy_url is not None:
            try:
                self._proxy_url = await self._new_proxy_url()
            except Exception as exc:  # noqa: BLE001 - rotation is best-effort
                logger.warning("Could not rotate proxy session: %s", exc)
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110 - closing a dead session may throw
            pass
        self.session = self._build_session(self._proxy_url)
        logger.info("Rotated to TLS profile %s", self._profile)

    async def get_json(self, url: str, params: dict | None = None, referer: str = "/") -> dict:
        """GET `url` and return the decoded JSON body.

        `referer` is a path relative to the origin. It is not cosmetic:
        without a `Referer` header Blibli's Cloudflare rule returns 403 even
        on a perfect JA3, so it is always sent.
        """
        headers = {**BASE_HEADERS, "Referer": ORIGIN + referer}
        last_error = "unknown"

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(url, params=params, headers=headers)
            except Exception as exc:  # noqa: BLE001 - network faults are retryable
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Request error (attempt %d): %s", attempt + 1, last_error)
            else:
                if not _is_blocked(response):
                    try:
                        payload = response.json()
                    except Exception as exc:  # noqa: BLE001
                        raise UpstreamShapeError(
                            f"{url} returned {response.status_code} with a non-JSON body "
                            f"({response.headers.get('content-type')}): {exc}"
                        ) from exc
                    if not isinstance(payload, dict):
                        raise UpstreamShapeError(
                            f"{url} returned JSON that is not an object: {type(payload).__name__}"
                        )
                    if "data" not in payload:
                        # Some Blibli endpoints answer "nothing more here"
                        # with a 404 error envelope instead of an empty
                        # list. Normalise it to an empty page so the
                        # caller's stop condition fires, rather than
                        # raising a false schema-change alarm.
                        if response.status_code == 404 and "errors" in payload:
                            logger.info("End of list at %s (%s)", url, payload.get("status"))
                            return {**payload, "data": []}
                        raise UpstreamShapeError(
                            f"{url} returned JSON without a `data` key -- upstream shape "
                            f"changed. Got HTTP {response.status_code}, keys: {list(payload)[:10]}"
                        )
                    return payload
                last_error = f"blocked with HTTP {response.status_code}"
                logger.warning(
                    "Blocked on %s (attempt %d, profile %s): %s",
                    url, attempt + 1, self._profile, last_error,
                )
                await self._rotate()

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))

        raise BlockedError(f"{url} still blocked after {MAX_RETRIES} attempts: {last_error}")

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
