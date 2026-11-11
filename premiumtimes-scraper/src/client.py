"""HTTP client wrapper -- warmup, retry, block detection.

No JA3/TLS-fingerprint WAF challenge was found on premiumtimesng.com during
recon (every profile in the ladder gets clean 200s). Retry/backoff
scaffolding is kept anyway per portfolio convention -- and here it also
carries a site-specific fix: a stale Cloudflare edge-cached JS-challenge
page occasionally sticks to a specific article URL (see constants.py and
CRAWLING_METHOD.md). Plain retries against the SAME url would keep hitting
that same cached response, so on a detected block the retry appends a
cache-busting query parameter to force a cache MISS at the edge.
"""

import asyncio
from urllib.parse import urlparse, urlunparse

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
    b"Pardon Our Interruption",
    b"_fs_ch_",
    b"Request unsuccessful",
    # premiumtimesng.com-specific: stale edge-cached slowAES JS cookie
    # challenge (see constants.py / CRAWLING_METHOD.md).
    b"slowAES",
    b"TZTC=",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


def _cache_bust(url: str, attempt: int) -> str:
    """Append/refresh a `_ptscb` query param to dodge a stale edge cache."""
    parsed = urlparse(url)
    query = parsed.query
    parts = [p for p in query.split("&") if p and not p.startswith("_ptscb=")]
    parts.append(f"_ptscb={attempt}")
    return urlunparse(parsed._replace(query="&".join(parts)))


class PremiumTimesClient:
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
        target = url
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, target, **kwargs)
                if is_blocked(r):
                    # A 403/429/503 is a normal transient block -- back off
                    # and retry the same URL. A 200-with-challenge-body is
                    # the stale-edge-cache quirk -- cache-bust immediately,
                    # no point re-requesting the exact same cached URL.
                    target = _cache_bust(url, attempt + 1)
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
