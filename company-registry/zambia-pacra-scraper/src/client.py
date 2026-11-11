"""HTTP client wrapper -- warmup, retry, block detection.

xatu.pacra.org.zm:8344 is a plain unauthenticated ASP.NET Web API
(`x-powered-by: ASP.NET`, `server: Microsoft-IIS/10.0`). No WAF, no CAPTCHA,
no session/viewstate token was observed anywhere in this path -- confirmed
with a bare request carrying none of the frontend SPA's own headers, and
with 5 rapid back-to-back calls with no throttling. `curl_cffi` TLS
impersonation is used anyway as this portfolio's default posture, not
because a block was ever seen. See constants.py / CRAWLING_METHOD.md.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
    WARMUP_URL,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
    b"Access Denied",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class PacraClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._warm = False

    async def init_session(self):
        if self._warm:
            return
        # Warm against the SPA shell, not the API host, so an eventual WAF
        # in front of the SPA (none observed) would surface here first.
        r = await self.session.get(WARMUP_URL)
        if r.status_code != 200:
            raise RuntimeError(f"Warmup failed: {r.status_code}")
        self._warm = True

    async def get(self, url: str, **kwargs):
        await self.init_session()
        return await self._with_retry("GET", url, **kwargs)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
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
