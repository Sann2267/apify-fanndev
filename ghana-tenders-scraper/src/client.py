"""HTTP client wrapper for GHANEPS's public listing and tender-detail pages.

No login, no CSRF handshake needed to read -- every URL here is a plain GET
that returns a fully server-rendered HTML page (see CRAWLING_METHOD.md).
Pagination on the listing pages uses a numeric "widget id" embedded in the
page's own sort/page-nav links (`?d-<id>-p=<n>`); we discover it fresh from
page 1 of each run rather than hardcoding it, since it's an internal
DisplayTag-style component id that could change on a future redeploy.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

WIDGET_ID_RE = re.compile(r"d-(\d+)-(?:s|p|n|o)=")


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
            # Both are caught explicitly per guardian-nigeria-scraper's
            # documented fix (and ghana-rgd-scraper's client.py).
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


def extract_widget_id(html_text: str) -> str | None:
    m = WIDGET_ID_RE.search(html_text)
    return m.group(1) if m else None


async def fetch_list_page(path: str, query: str, page: int, widget_id: str | None, proxy_url: str | None = None) -> str:
    """Fetches one page of a listing view. `widget_id` must be None for page 1
    (it doesn't exist yet) and the id discovered from page 1's response for
    page 2+."""
    if page == 1:
        url = f"{path}?{query}" if query else path
    else:
        if not widget_id:
            raise FetchFailed(f"page={page} requested but no widget_id available (path={path})")
        page_query = f"d-{widget_id}-p={page}"
        if query:
            page_query = f"{page_query}&{query}"
        url = f"{path}?{page_query}"
    return await get_with_retries(url, proxy_url=proxy_url)


async def fetch_detail_page(resource_id: str, proxy_url: str | None = None) -> str:
    from src.constants import DETAIL_PATH

    url = f"{DETAIL_PATH}?resourceId={resource_id}"
    return await get_with_retries(url, proxy_url=proxy_url)
