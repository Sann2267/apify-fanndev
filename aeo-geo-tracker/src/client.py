"""HTTP client wrapper -- retry, block detection.

Two additional backends (Google AI Overview, DuckDuckGo AI Chat) were
investigated and ruled out as HTTP-only dead ends during development --
both require executing real JavaScript (a client-side hydration step for
Google, a proof-of-work-style JS challenge for DuckDuckGo) that this
project's HTTP-only constraint doesn't permit solving. See
CRAWLING_METHOD.md for the full evidence trail on both. Only the Bing
backend, which needs neither, is shipped.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

GENERIC_BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
]


class Client:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        return await self._with_retry("GET", url, params=params, headers=headers)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (403, 407, 503) or _is_generic_block(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()


def _is_generic_block(response) -> bool:
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in GENERIC_BLOCK_MARKERS)
