"""HTTP client wrapper -- retry, block detection.

topcv.vn sits behind Cloudflare but no active challenge was observed
during recon (see CRAWLING_METHOD.md) -- `curl_cffi chrome124` gets clean
200s with full page content on every page type tested. Retry/backoff
scaffolding is kept anyway per portfolio convention.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

BLOCK_MARKERS = [
    b"Just a moment",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"_px-captcha",
    b"id=\"challenge-error-text\"",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class TopCVClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get(self, url: str, params: dict | None = None):
        return await self._with_retry("GET", url, params=params)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, allow_redirects=True, **kwargs)
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
