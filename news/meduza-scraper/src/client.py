"""HTTP client wrapper -- warmup, retry, block detection.

No active WAF challenge was found on meduza.io during recon (see
CRAWLING_METHOD.md) -- it sits behind Cloudflare but never issues a JS
challenge to curl_cffi chrome124. Retry/backoff scaffolding is kept anyway
per portfolio convention.
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
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"_fs_ch_",
    b"Request unsuccessful",
]
# NOTE: the portfolio-wide default list also includes b"challenge-platform",
# deliberately dropped here. meduza.io injects a passive Cloudflare bot-
# management beacon (`/cdn-cgi/challenge-platform/scripts/jsd/main.js`,
# `window.__CF$cv$params`) into the <head> of every page it serves --
# including normal 200s and real 404s, not just active challenges. Keeping
# that marker made is_blocked() true on 100% of responses (confirmed on a
# synthetic 404 during recon: real HTTP 404, correct body, zero challenge
# markup, yet it matched "challenge-platform" and retry-looped forever).
# An actual Cloudflare JS challenge is still caught by "Just a moment" /
# "cf-mitigated" / the 403/429/503 status check below.


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class MeduzaClient:
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
