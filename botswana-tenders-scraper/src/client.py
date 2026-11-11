"""HTTP client for Botswana ministry tender pages.

Neither `finance.gov.bw` nor `moh.gov.bw` showed a TLS-fingerprint gate or
WAF during recon (see `constants.py`) -- `curl_cffi` is used for portfolio
consistency and residential-proxy compatibility, but plain `requests`/
`httpx` would also clear both targets.

The retry loop wraps request calls in a broad `except Exception`, same
pattern as every other actor in this portfolio: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    FINANCE_RSS_URL,
    HEALTH_TENDERS_URL,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)


class BotswanaTendersClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (429, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} transient response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_finance_rss(self) -> str:
        r = await self._with_retry("GET", FINANCE_RSS_URL)
        if r.status_code != 200:
            raise RuntimeError(f"GET {FINANCE_RSS_URL} -> HTTP {r.status_code}")
        return r.text

    async def fetch_health_tenders_page(self) -> str:
        r = await self._with_retry("GET", HEALTH_TENDERS_URL)
        if r.status_code != 200:
            raise RuntimeError(f"GET {HEALTH_TENDERS_URL} -> HTTP {r.status_code}")
        return r.text

    async def close(self):
        await self.session.close()
