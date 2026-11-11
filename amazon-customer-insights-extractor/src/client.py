"""HTTP client: TLS-profile rotation, currency pinning, backoff."""

import asyncio
import logging
import random

from curl_cffi import requests

from src.constants import (
    MARKETPLACE_CURRENCY,
    MIN_PRODUCT_PAGE_BYTES,
    TLS_PROFILE_LADDER,
)
from src.insights import is_blocked

logger = logging.getLogger(__name__)


class Blocked(RuntimeError):
    """Amazon served a bot wall for every profile tried."""


class AmazonClient:
    """One product-page fetcher.

    Two Amazon-specific behaviours are baked in here:

    * The /dp/ surface accepts only a narrow set of TLS fingerprints, and it
      is a *different* set from Amazon search or Best Sellers. The ladder is
      rotated per attempt.
    * Blocks arrive as HTTP 200 with a ~3.8 KB body, so a successful status
      proves nothing -- responses are validated by size and content.
    """

    def __init__(self, marketplace: str = "com", proxy_url=None, timeout: int = 45,
                 proxy_configuration=None):
        self.marketplace = marketplace
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.proxy_configuration = proxy_configuration
        self._profile_index = 0
        self._session_counter = 0

    async def rotate_session(self) -> bool:
        """Move to a fresh proxy exit IP.

        Whether Amazon serves the full or the reduced product page tracks the
        requesting IP/session, not the ASIN, so a new exit is the one lever
        that can turn an insight-less response into a complete one.
        """
        if not self.proxy_configuration:
            return False
        self._session_counter += 1
        try:
            self.proxy_url = await self.proxy_configuration.new_url(
                session_id=f"insights{self._session_counter}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not rotate proxy session: %s", exc)
            return False
        return True

    @property
    def _cookies(self) -> dict:
        # Without i18n-prefs, Amazon prices from the egress IP: an Indonesian
        # exit returned "IDR 336,939.57" for a $19.99 item. The query param
        # `&currency=` and `lc-main` alone were both measured to be ignored.
        return {
            "i18n-prefs": MARKETPLACE_CURRENCY.get(self.marketplace, "USD"),
            "lc-main": "en_US",
        }

    def _headers(self, referer=None) -> dict:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if referer else "none",
            "Sec-Fetch-User": "?1",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _fetch_sync(self, url: str, profile: str, referer):
        kwargs = {"impersonate": profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        session = requests.Session(**kwargs)
        try:
            response = session.get(url, headers=self._headers(referer), cookies=self._cookies)
            return response.status_code, response.text
        finally:
            session.close()

    async def get_product(self, url: str, referer=None, max_attempts: int = 6) -> str:
        """Fetch a product page, rotating fingerprints until one is served."""
        last = "no attempt made"
        for attempt in range(max_attempts):
            profile = TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]
            self._profile_index += 1
            try:
                status, body = await asyncio.to_thread(self._fetch_sync, url, profile, referer)
            except Exception as exc:  # network/TLS failures are expected here
                last = f"{type(exc).__name__}: {exc}"
                logger.warning("fetch error (%s, attempt %s): %s", profile, attempt + 1, last)
            else:
                if status == 404:
                    raise Blocked(f"404 -- no such product ({url})")
                if status == 200 and not is_blocked(body):
                    return body
                last = (f"HTTP {status}, {len(body)}B "
                        f"({'bot wall' if status == 200 else 'error page'})")
                logger.warning("blocked via %s (attempt %s): %s", profile, attempt + 1, last)

            # Exponential backoff with jitter; Amazon tightens quickly when
            # retries arrive on a fixed cadence.
            if attempt < max_attempts - 1:
                await asyncio.sleep(min(2 ** attempt, 20) + random.uniform(0, 1.5))

        raise Blocked(f"all {max_attempts} attempts blocked -- last: {last}")

    async def close(self):
        return None


__all__ = ["AmazonClient", "Blocked", "MIN_PRODUCT_PAGE_BYTES"]
