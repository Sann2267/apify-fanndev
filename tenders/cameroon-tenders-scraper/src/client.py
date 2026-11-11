"""HTTP client wrapper for armp.cm's public listing and publication-detail
pages.

No login, no CSRF handshake needed to read -- every URL here is a plain GET
that returns a fully server-rendered HTML page (see CRAWLING_METHOD.md). The
server does set a Laravel `XSRF-TOKEN`/`armp_session` cookie pair on first
response, but it's session bookkeeping only -- these GETs work identically
with or without carrying cookies forward, so each request uses a fresh
session (matches the pattern used across this portfolio's other tender
actors).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


class NotFoundOrRestricted(Exception):
    """The publication id/type combination doesn't resolve to a real record.

    Confirmed empirically: armp.cm returns a generic Laravel HTTP 500 "Server
    Error" page for an id_publication that doesn't exist (tried id=1,
    id=999999999 -- both 500, both instant, both stable across repeat
    requests). This is NOT a login wall on viewing (every id pulled from a
    real listing page renders fully with zero auth, see CRAWLING_METHOD.md)
    and NOT a transient error worth retrying -- it's raised immediately,
    without going through the retry loop, the same way GHANEPS's CAS-login
    redirect is treated as a per-record not_found rather than general block.
    """


async def _get(session: AsyncSession, url: str) -> str:
    r = await session.get(url, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} returned {r.status_code}")
    return r.text


async def get_with_retries(url: str, proxy_url: str | None = None) -> str:
    """Runs a single GET with retries. Returns the raw HTML.

    A handful of requests during recon timed out on `chrome124` and
    succeeded on immediate retry with the exact same profile -- ordinary
    transient flakiness on this host, not a TLS-fingerprint block (armp.cm
    carries no WAF/CDN fingerprint at all: plain Apache + PHP, no cf-ray, no
    bot-challenge markers). Retries alone are enough; no profile ladder
    needed.
    """
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
            # CONNECT tunnel, DNS failure, TLS handshake error, timeout, etc.)
            # does NOT inherit from Python's builtin ConnectionError -- its
            # MRO is RequestException -> CurlError -> OSError, a parallel
            # hierarchy. Both are caught explicitly, per the portfolio-wide
            # Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


def build_list_url(path: str, query: str, page: int) -> str:
    """Builds a listing page URL. page=1 and page omitted are confirmed
    byte-identical, but always passing it explicitly keeps the pagination
    logic simple and makes each request's page self-descriptive in logs."""
    sep = "&" if query else ""
    page_query = f"{query}{sep}page={page}" if query or page > 1 else ""
    if not page_query:
        return path
    return f"{path}?{page_query}"


async def fetch_list_page(path: str, query: str, page: int, proxy_url: str | None = None) -> str:
    url = build_list_url(path, query, page)
    return await get_with_retries(url, proxy_url=proxy_url)


async def fetch_detail_page(type_publication: str, id_publication: str, proxy_url: str | None = None) -> str:
    from src.constants import DETAIL_PATH

    url = f"{DETAIL_PATH}?type_publication={type_publication}&id_publication={id_publication}"
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 500:
                raise NotFoundOrRestricted(
                    f"GET {url} returned 500 -- armp.cm's stable signature for an invalid/inaccessible id"
                )
            if r.status_code != 200:
                raise FetchFailed(f"GET {url} returned {r.status_code}")
            return r.text
        except NotFoundOrRestricted:
            raise  # deterministic, not transient -- do not retry
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # See the NOTE in get_with_retries above re: curl_cffi's parallel
            # RequestException/ConnectionError MRO -- both listed here too.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")
