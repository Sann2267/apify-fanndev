"""HTTP client wrapper for PPDA's public procurement-notice pages.

A single stateless GET per notice type -- no session, no CSRF, no cookies,
no query parameters (each page renders its whole current notice board into
one response; DataTables' client-side JS only affects sort/search/paginate
inside the browser).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import BASE_HOST, HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """The GET never produced a usable response."""


async def _one_attempt(path: str, proxy_url: str | None) -> str:
    session = AsyncSession(
        impersonate=TLS_PROFILE,
        proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
        timeout=60,
    )
    url = f"{BASE_HOST}/{path}"
    try:
        r = await session.get(url, headers=HEADERS)
        if r.status_code != 200:
            raise FetchFailed(f"GET {url} returned {r.status_code}")
        if "ppda" not in r.text.lower():
            # A cheap marker present on every genuine render of this site --
            # its absence means we got something else (WAF page, maintenance
            # page, DNS-hijack landing page, a redesign that dropped the
            # branding entirely).
            raise FetchFailed(f"response from {url} missing 'ppda' marker -- page shape has likely changed")
        return r.text
    finally:
        await session.close()


async def fetch_notice_page(path: str, proxy_url: str | None = None) -> str:
    """Runs the GET for one notice-board path, with retries. Returns the raw HTML page."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await _one_attempt(path, proxy_url)
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per portfolio-wide convention.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts fetching {BASE_HOST}/{path}: {last_exc!r}")
