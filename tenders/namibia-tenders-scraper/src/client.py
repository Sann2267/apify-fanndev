"""HTTP client wrapper for CPBN's public "Bids" listing and bid-detail pages.

No login, no CSRF handshake needed to read -- every URL here is a plain GET
that returns a fully server-rendered HTML page (see CRAWLING_METHOD.md). Each
listing view returns every row it has in one response (the page's own
DataTables widget only paginates client-side via JS), so there is no
server-side pagination to walk.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import DETAIL_PATH, HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


async def _get(session: AsyncSession, url: str) -> str:
    r = await session.get(url, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} returned {r.status_code}")
    return r.text


async def get_with_retries(url: str, proxy_url: str | None = None) -> str:
    """Runs a single GET with retries. Returns the raw HTML."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            return await _get(session, url)
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException (raised on a failed proxy
            # CONNECT tunnel, DNS failure, TLS handshake error, etc.) does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per the portfolio-wide Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


async def fetch_list_page(path: str, proxy_url: str | None = None) -> str:
    """Fetches a full "Bids" listing view. Every row is embedded in this one
    response -- there is no page number to request."""
    return await get_with_retries(path, proxy_url=proxy_url)


async def fetch_detail_page(bid_id: str, proxy_url: str | None = None) -> str:
    url = f"{DETAIL_PATH}/{bid_id}"
    return await get_with_retries(url, proxy_url=proxy_url)
