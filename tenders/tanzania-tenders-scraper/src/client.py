"""HTTP client wrapper for NeST's public OCDS JSON API.

No login, no CSRF handshake, no API key -- every URL here is a plain GET
that returns JSON directly (see CRAWLING_METHOD.md). The only real quirk is
that the server rate-limits fairly aggressively (a bare 403 with an empty
body after a handful of quick requests) and its "cursor" query parameter is
accepted but not actually honoured -- see `list_records_since` below for the
"advance since" workaround used instead of trusting the cursor/next link.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    HEADERS,
    MAX_RETRIES,
    RECORD_DETAIL_PATH,
    RECORDS_PATH,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


class RecordNotFound(Exception):
    """A detail GET for a specific ocid came back 404 -- genuinely no such record."""


async def _get_json(url: str, proxy_url: str | None = None):
    """Runs a single GET with retries. Returns the parsed JSON body.

    Raises RecordNotFound on a clean 404 (no retry -- that's a real answer,
    not a transient failure). Raises FetchFailed if every retry is exhausted
    on a non-200/non-404 status, an empty body, or a connection-level error.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.get(url, headers=HEADERS)
            if r.status_code == 404:
                raise RecordNotFound(url)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"GET {url} returned {r.status_code} ({len(r.content)} bytes)")
            return r.json()
        except RecordNotFound:
            raise
        except (FetchFailed, RequestException, ConnectionError, TimeoutError, ValueError) as e:
            # NOTE: curl_cffi's own RequestException (raised on a failed proxy
            # CONNECT tunnel, DNS failure, TLS handshake error, etc.) does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly, per the portfolio-wide Babak 22b fix.
            # ValueError also covers a JSON-decode failure on a 200 with a
            # truncated/corrupt body, observed occasionally during recon.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


async def fetch_records_page(since: str, proxy_url: str | None = None) -> dict:
    """Fetches one page (fixed 5 records server-side) of the records feed for
    records dated >= `since` (ISO 8601, e.g. '2026-06-01T00:00:00Z').

    `cursor` is always sent as 0 -- the server does not actually use it (see
    module docstring) so there is no point varying it; real pagination is
    done by the caller advancing `since`.
    """
    url = f"{RECORDS_PATH}?cursor=0&since={since}"
    return await _get_json(url, proxy_url=proxy_url)


async def fetch_record_detail(ocid: str, proxy_url: str | None = None) -> dict:
    """Fetches the single compiled record for one ocid. Raises RecordNotFound
    on an invalid/unknown ocid."""
    url = RECORD_DETAIL_PATH.format(ocid=ocid)
    return await _get_json(url, proxy_url=proxy_url)
