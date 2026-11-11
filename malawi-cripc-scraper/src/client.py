"""HTTP client for CRIPC/MBRS's public HTML search page.

Unlike Uganda's URSB (a plain JSON REST API), Malawi's `mbrs.gov.mw/search`
server-renders the results page as HTML -- there is no separate JSON
endpoint to call, so this client fetches whole pages and hands them to
`extractor.py` to parse. See `constants.py` for the full recon summary.

Retry loop wraps ALL request calls in a broad `except Exception`, same fix
as `botswana-cipa-scraper/src/client.py` and `uganda-ursb-scraper/src/
client.py`: `curl_cffi`'s own exception hierarchy (`CurlError` -> `OSError`)
does NOT inherit from Python's builtin `ConnectionError`/`TimeoutError`
despite sharing class names, so a narrower except list silently misses real
transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEARCH_PATH,
    TLS_PROFILE,
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


class MBRSClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    last_exc = RuntimeError(f"HTTP {r.status_code} blocked/prohibited response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_search_page(self, search_type: str, query: str, page: int) -> str:
        params = {"type": search_type, "q": query, "page": page}
        r = await self._with_retry("GET", f"{BASE_URL}{SEARCH_PATH}", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_PATH}?type={search_type}&q={query!r}&page={page} -> HTTP {r.status_code}")
        return r.text

    async def fetch_owner_detail(self, owner_id: str) -> str:
        r = await self._with_retry("GET", f"{BASE_URL}{SEARCH_PATH}/{owner_id}", params={"type": "owner"})
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_PATH}/{owner_id}?type=owner -> HTTP {r.status_code}")
        return r.text

    async def close(self):
        await self.session.close()
