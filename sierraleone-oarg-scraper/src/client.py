"""HTTP client wrapper for OARG's Company Search tool.

Each search is a single stateless GET -- no session, no CSRF, no cookies.
Retries are per-attempt on the whole request since a transient failure
(timeout, proxy hiccup) has no state to preserve between attempts.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import BASE_URL, HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class SearchFailed(Exception):
    """The GET never produced a usable response."""


async def _one_attempt(query: str, proxy_url: str | None) -> str:
    session = AsyncSession(
        impersonate=TLS_PROFILE,
        proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
        timeout=60,
    )
    try:
        r = await session.get(BASE_URL, params={"query": query}, headers=HEADERS)
        if r.status_code != 200:
            raise SearchFailed(f"search GET returned {r.status_code}")
        if "az-content-body" not in r.text:
            # The one HTML marker present on every genuine render of this
            # page (results, available, or too-short-query) -- its absence
            # means we got something else entirely (WAF page, maintenance
            # page, DNS-hijack landing page, etc).
            raise SearchFailed("response missing 'az-content-body' marker -- page shape has likely changed")
        return r.text
    finally:
        await session.close()


async def search(query: str, proxy_url: str | None = None) -> str:
    """Runs the GET with retries. Returns the raw HTML page."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await _one_attempt(query, proxy_url)
        except (SearchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per portfolio-wide convention.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
    raise SearchFailed(f"Exhausted {MAX_RETRIES} attempts for query={query!r}: {last_exc!r}")
