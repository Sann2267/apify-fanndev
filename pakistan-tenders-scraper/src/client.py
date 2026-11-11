"""HTTP client for epms.ppra.gov.pk (Pakistan's PPRA e-Publish & Monitoring
System).

No WAF, no TLS-fingerprint gate, no session/cookie requirement observed
anywhere under `/public/tenders/*` during recon -- plain `curl` with a
standard desktop User-Agent (no TLS impersonation at all) got clean 200s
throughout. `curl_cffi` `chrome124` is used anyway for portfolio-wide
consistency. Each call is independent/stateless (no priming step needed,
unlike `nepal-tenders-scraper`'s Bolpatra).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    DEFAULT_HEADERS,
    DETAIL_URL,
    INVOICE_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request never produced a usable 200 response after retries."""


class PpraClient:
    def __init__(self, proxy_url: str | None = None):
        self.session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code != 200:
                    raise FetchFailed(f"{method} {url} -> HTTP {r.status_code}: {r.text[:300]!r}")
                return r
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                # NOTE: curl_cffi's own ConnectionError/RequestException does
                # NOT inherit from Python's builtin ConnectionError -- its MRO
                # is RequestException -> CurlError -> OSError, a parallel
                # hierarchy. Both listed, per this project's portfolio-wide
                # Babak 22b fix.
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {method} {url!r}: {last_exc!r}")

    async def fetch_listing(self, base_url: str, params: dict) -> str:
        r = await self._with_retry("GET", base_url, params=params)
        return r.text

    async def fetch_detail(self, tender_no: str) -> str:
        r = await self._with_retry("GET", f"{DETAIL_URL}/{tender_no}")
        return r.text

    async def close(self):
        await self.session.close()


def invoice_url(tender_no: str) -> str:
    return f"{INVOICE_URL}/{tender_no}"
