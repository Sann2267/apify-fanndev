"""HTTP client wrapper for ESPPRA's public tender / award-intention /
suspended-supplier pages.

No login, no CSRF handshake needed to read any of these -- every URL here is
a plain GET (see CRAWLING_METHOD.md). Pagination on the "jobbox" listing
pages uses a simple `?Page=<n>&txtKeyword=<kw>` query string discovered from
the page's own "Next >>" links -- no session/token needed between pages.

TLS cert gotcha: esppra.co.sz's certificate chain is missing an intermediate
-- curl_cffi raises CertificateVerifyError on every impersonation profile
with default verification. Confirmed via plain `curl` too (exit 60). Every
request here uses verify=False as the workaround, the same pattern already
documented for nepal-tenders-scraper / nepal-ocr-scraper's identical symptom.
"""

import asyncio
from urllib.parse import quote

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import HEADERS, LIST_CONFIGS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


async def _get(session: AsyncSession, url: str) -> str:
    r = await session.get(url, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} returned {r.status_code}")
    return r.text


async def get_with_retries(url: str, proxy_url: str | None = None) -> str:
    """Runs a single GET with retries. Returns the raw response body (HTML or JSON text)."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
            verify=False,  # missing intermediate cert on esppra.co.sz -- see module docstring
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


async def fetch_list_page(list_type: str, page: int, keyword: str, proxy_url: str | None = None) -> str:
    """Fetches one page of a listing view.

    `suspended_suppliers` ("json_table") ignores `page`/`keyword` -- it's a
    single DataTables call that returns the whole (small) register at once.
    """
    cfg = LIST_CONFIGS[list_type]
    if cfg["kind"] == "json_table":
        return await get_with_retries(cfg["path"], proxy_url=proxy_url)

    kw = quote(keyword or "", safe="")
    url = f"{cfg['path']}?Page={page}&txtKeyword={kw}"
    return await get_with_retries(url, proxy_url=proxy_url)
