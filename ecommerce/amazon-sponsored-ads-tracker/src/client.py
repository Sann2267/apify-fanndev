"""HTTP client for Amazon search result pages."""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    CURRENCIES,
    LOCALES,
    MAX_RETRIES,
    MIN_PAGE_BYTES,
    PAGE_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

CAPTCHA_MARKERS = (
    b"Robot Check",
    b"Enter the characters you see below",
    b"/errors/validateCaptcha",
    b"Type the characters you see in this image",
)


class BlockedError(Exception):
    """Every retry and every verified profile still hit Amazon's block page."""


class CaptchaError(Exception):
    """Amazon served a CAPTCHA; this actor never solves them."""


class AmazonClient:
    def __init__(self, marketplace: str = "com", proxy_url=None, new_proxy_url=None):
        self.marketplace = marketplace
        self._new_proxy_url = new_proxy_url
        self._profile_index = 0
        self._proxy_url = proxy_url
        self.session = self._build_session(proxy_url)

    @property
    def _profile(self) -> str:
        return TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]

    @property
    def _cookies(self) -> dict:
        """Force the marketplace currency regardless of egress IP.

        Without this, prices come back in the currency of whatever country
        the proxy exits from -- an Indonesian egress returns IDR on
        amazon.com, which would silently corrupt any price comparison.
        """
        return {
            "i18n-prefs": CURRENCIES.get(self.marketplace, "USD"),
            "lc-main": LOCALES.get(self.marketplace, "en_US"),
        }

    def _build_session(self, proxy_url) -> AsyncSession:
        return AsyncSession(
            impersonate=self._profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )

    async def _rotate(self) -> None:
        self._profile_index += 1
        if self._new_proxy_url is not None:
            try:
                self._proxy_url = await self._new_proxy_url()
            except Exception as exc:  # noqa: BLE001 - rotation is best-effort
                logger.warning("Could not rotate proxy session: %s", exc)
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
        self.session = self._build_session(self._proxy_url)
        logger.info("Rotated to TLS profile %s", self._profile)

    async def get_search(self, url: str) -> str:
        """Fetch a search results page.

        Amazon's block response is a ~2.7 KB "Sorry! Something went wrong!"
        page served with a 503, so a short body is treated as a block even
        when the status looks survivable. Rotation through the verified
        profile ladder is what clears it.
        """
        last = "unknown"
        captchas = 0
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(
                    url, headers=PAGE_HEADERS, cookies=self._cookies
                )
            except Exception as exc:  # noqa: BLE001 - network faults are retryable
                last = f"{type(exc).__name__}: {exc}"
            else:
                body = response.content[:8192] if response.content else b""
                if any(marker in body for marker in CAPTCHA_MARKERS):
                    captchas += 1
                    last = "captcha served"
                    logger.warning("CAPTCHA on attempt %d (%s)", attempt + 1, self._profile)
                    await self._rotate()
                elif response.status_code == 200 and len(response.text) >= MIN_PAGE_BYTES:
                    return response.text
                else:
                    last = f"HTTP {response.status_code}, {len(response.text)} bytes"
                    logger.warning(
                        "Blocked page on attempt %d (%s): %s", attempt + 1, self._profile, last
                    )
                    await self._rotate()

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))

        if captchas:
            raise CaptchaError(
                f"Amazon served a CAPTCHA on {captchas} of {MAX_RETRIES} attempts for {url}. "
                "This actor does not solve CAPTCHAs -- use a residential proxy and raise "
                "delaySeconds."
            )
        raise BlockedError(f"{url} could not be fetched after {MAX_RETRIES} attempts: {last}")

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
