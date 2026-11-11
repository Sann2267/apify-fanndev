"""HTTP client wrapper for NPPA's "Bids / Tenders" page.

A single stateless GET -- no session, no CSRF, no cookies, no query
parameters (the whole current tender board is rendered into one page).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import BASE_URL, HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """The GET never produced a usable response."""


async def _one_attempt(proxy_url: str | None) -> str:
    session = AsyncSession(
        impersonate=TLS_PROFILE,
        proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
        timeout=60,
    )
    try:
        r = await session.get(BASE_URL, headers=HEADERS)
        if r.status_code != 200:
            raise FetchFailed(f"GET {BASE_URL} returned {r.status_code}")
        if "tablepress" not in r.text.lower():
            # The one marker present on every genuine render of this page --
            # its absence means we got something else (WAF page, maintenance
            # page, DNS-hijack landing page, redesign that dropped the table).
            raise FetchFailed("response missing 'tablepress' marker -- page shape has likely changed")
        return r.text
    finally:
        await session.close()


async def fetch_bid_page(proxy_url: str | None = None) -> str:
    """Runs the GET with retries. Returns the raw HTML page."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await _one_attempt(proxy_url)
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per portfolio-wide convention.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts fetching {BASE_URL}: {last_exc!r}")
