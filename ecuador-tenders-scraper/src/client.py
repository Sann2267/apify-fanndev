"""HTTP client wrapper for SERCOP's public OCDS search and record endpoints.

No login, no CSRF handshake, no API key -- see CRAWLING_METHOD.md. Both
endpoints return plain JSON directly (no zip/binary wrapper like Nigeria's
NOCOPO). `search_ocds` requires both `year` and `search` (>= 3 chars)
upstream -- there is no bare "list everything" call, so this actor's list
mode always takes a keyword. `record` takes a single `ocid` and always
returns 200 (an unknown ocid comes back with an empty `records` array rather
than a 404), so this actor treats that case as `RecordNotFound`.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    HEADERS,
    MAX_RETRIES,
    RECORD_ENDPOINT,
    RETRY_DELAY_BASE,
    SEARCH_ENDPOINT,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET never produced a usable 200 JSON response after retries."""


class RecordNotFound(Exception):
    """A detail GET for a specific ocid came back genuinely empty -- no such record."""


async def _get(url: str, params: dict, proxy_url: str | None = None):
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.get(url, headers=HEADERS, params=params)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"GET {url} returned {r.status_code} ({len(r.content)} bytes)")
            return r
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError (raised on
            # a failed proxy CONNECT tunnel, DNS failure, TLS handshake error,
            # etc.) does NOT inherit from Python's builtin ConnectionError --
            # its MRO is RequestException -> CurlError -> OSError, a parallel
            # hierarchy. Both are caught explicitly, per the portfolio-wide
            # Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r} params={params!r}: {last_exc!r}")


async def fetch_search_page(
    year: int,
    search: str,
    page: int,
    buyer: str = "",
    supplier: str = "",
    proxy_url: str | None = None,
) -> dict:
    """One page of SERCOP's `search_ocds` keyword search. `year` and `search`
    are always sent -- both are mandatory upstream (see CRAWLING_METHOD.md).
    `buyer`/`supplier` are only included when non-empty, matching how the
    platform's own search form omits them when unused."""
    params: dict = {"year": year, "search": search, "page": page}
    if buyer:
        params["buyer"] = buyer
    if supplier:
        params["supplier"] = supplier
    r = await _get(SEARCH_ENDPOINT, params, proxy_url=proxy_url)
    try:
        return r.json()
    except ValueError as e:
        raise FetchFailed(f"search page year={year} search={search!r} page={page} returned non-JSON body: {e!r}") from e


async def fetch_record(ocid: str, proxy_url: str | None = None) -> dict:
    """Fetches the full OCDS release history for one ocid. Raises
    RecordNotFound when the upstream `releases` array comes back empty (an
    unknown/malformed ocid still returns 200 -- confirmed live: SERCOP's own
    docs page shows the response nested under a top-level `records` array,
    but the live response is actually a flat OCDS release *package*: `uri`/
    `license`/`version`/`releases`/`publisher`/`extensions`/`publishedDate`/
    `publicationPolicy` at the top level, no `records` wrapper. See
    CRAWLING_METHOD.md.)."""
    r = await _get(RECORD_ENDPOINT, {"ocid": ocid}, proxy_url=proxy_url)
    try:
        data = r.json()
    except ValueError as e:
        raise FetchFailed(f"record ocid={ocid!r} returned non-JSON body: {e!r}") from e

    if not isinstance(data, dict) or not data.get("releases"):
        raise RecordNotFound(ocid)
    return data
