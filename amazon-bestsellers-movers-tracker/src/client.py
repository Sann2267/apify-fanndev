"""HTTP client for Amazon's ranked list pages."""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    MAX_RETRIES,
    PAGE_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

# Amazon answers a bot-detected request with a CAPTCHA/"Robot Check" page
# that still carries HTTP 200, so the body is what has to be inspected.
BLOCK_MARKERS = (
    b"Robot Check",
    b"Enter the characters you see below",
    b"api-services-support@amazon.com",
    b"/errors/validateCaptcha",
    b"Type the characters you see in this image",
)


class BlockedError(Exception):
    """Every retry and every TLS profile was exhausted while still gated."""


class CaptchaError(Exception):
    """Amazon served a CAPTCHA.

    Per this project's no-captcha-solver policy this is never solved; the
    URL is recorded as failed and the run continues.
    """


class NotFound(Exception):
    """The category or list page does not exist."""


def _is_captcha(response) -> bool:
    body = response.content[:8192] if response.content else b""
    return any(marker in body for marker in BLOCK_MARKERS)


class AmazonClient:
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

    async def get_page(self, url: str) -> str:
        """Fetch a ranked list page as HTML.

        A CAPTCHA is retried with a fresh fingerprint and IP a couple of
        times -- rotation genuinely clears it -- and then reported rather
        than solved.
        """
        last = "unknown"
        captchas = 0
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(url, headers=PAGE_HEADERS)
            except Exception as exc:  # noqa: BLE001 - network faults are retryable
                last = f"{type(exc).__name__}: {exc}"
                logger.warning("Request error (attempt %d): %s", attempt + 1, last)
            else:
                if response.status_code == 404:
                    raise NotFound(f"{url} returned 404")
                if _is_captcha(response):
                    captchas += 1
                    last = "captcha served"
                    logger.warning(
                        "CAPTCHA on %s (attempt %d, profile %s)", url, attempt + 1, self._profile
                    )
                    await self._rotate()
                elif response.status_code == 200 and len(response.text) > 30_000:
                    return response.text
                else:
                    last = f"HTTP {response.status_code}, {len(response.text)} bytes"
                    await self._rotate()

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))

        if captchas:
            raise CaptchaError(
                f"{url} served a CAPTCHA on {captchas} of {MAX_RETRIES} attempts. This actor "
                "does not solve CAPTCHAs -- use a residential proxy, or lower concurrency."
            )
        raise BlockedError(f"{url} could not be fetched after {MAX_RETRIES} attempts: {last}")

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
