"""HTTP client wrapper -- warmup, retry, block detection.

No JA3/TLS-fingerprint WAF challenge was found on leadership.ng during
recon (chrome124 gets clean 200s on homepage, article pages, and /feed/).
Retry/backoff scaffolding is kept anyway per portfolio convention, in case
of transient Cloudflare hiccups under load.
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
    b"Pardon Our Interruption",
    b"_fs_ch_",
    b"Request unsuccessful",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class LeadershipClient:
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
        # A plain self.session.get() call raises curl_cffi's own exception
        # types directly (Timeout, ConnectionError, etc. -- all subclasses of
        # curl_cffi.curl.CurlError, itself an OSError, NOT Python's builtin
        # ConnectionError) instead of returning a response. Caught here and
        # normalized to RuntimeError so a slow/unreachable proxy on warmup
        # surfaces as a clean per-item error record upstream instead of an
        # unhandled exception that crashes the whole run (portfolio-wide
        # Babak 22b fix -- see star-kenya-scraper/nypost-scraper client.py).
        try:
            r = await self.session.get(WARMUP_URL)
        except Exception as e:  # noqa: BLE001 -- normalize any transport failure
            raise RuntimeError(f"Warmup failed: {e!r}") from e
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
