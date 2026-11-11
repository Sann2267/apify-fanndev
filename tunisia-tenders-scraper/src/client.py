"""HTTP client wrapper for TUNEPS's public tender ("Appel d'offres") JSON API.

No login, no CSRF handshake, no API key -- every call here is a plain POST
(list) or GET (detail) that returns JSON directly (see CRAWLING_METHOD.md).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    DETAIL_PATH,
    HEADERS,
    LIST_PATH,
    MAX_RETRIES,
    PUBLIC_YN_FILTER,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request never produced a usable 200 response after retries."""


class RecordNotFound(Exception):
    """A detail GET for a specific bid id came back 404/empty -- genuinely no such record."""


async def _request_json(method: str, url: str, *, json_body: dict | None = None, proxy_url: str | None = None):
    """Runs a single request with retries. Returns the parsed JSON body.

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
            # www.tuneps.tn's TLS chain is missing an intermediate certificate
            # (confirmed during recon: the same "unable to get local issuer
            # certificate" failure the portfolio has already hit on Nepal's
            # and Eswatini's government hosts) -- verify=False is required.
            verify=False,
        )
        try:
            if method == "GET":
                r = await session.get(url, headers=HEADERS)
            else:
                r = await session.post(url, headers=HEADERS, json=json_body)
            if r.status_code == 404:
                raise RecordNotFound(url)
            if r.status_code == 400:
                # Confirmed during recon: a non-numeric/malformed bid id hits a
                # Spring "Whitelabel Error Page" (HTML, not JSON) with a 400 --
                # a genuine "no such id" answer, not a transient failure.
                raise RecordNotFound(url)
            if r.status_code == 401:
                # Seen only when a required search filter/field is missing or
                # malformed -- see CRAWLING_METHOD.md. Not a login wall on the
                # confirmed-correct request shape this client always sends,
                # but surfaced distinctly in case upstream ever actually adds one.
                raise FetchFailed(f"{method} {url} returned 401 (unexpected auth requirement)")
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"{method} {url} returned {r.status_code} ({len(r.content)} bytes)")
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
            # truncated/corrupt body.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


def _build_search_body(limit: int, offset: int, sort_col: str, sort_dir: str, extra_filters: list[dict]) -> dict:
    return {
        "pagination": {"limit": limit, "offSet": offset},
        "sort": {"nameCol": sort_col, "direction": sort_dir},
        "dataSearch": [PUBLIC_YN_FILTER, *extra_filters],
        "listSort": [],
        "listCol": [],
    }


async def fetch_list_page(
    limit: int,
    offset: int,
    *,
    sort_col: str = "publicDt",
    sort_dir: str = "desc nulls last",
    extra_filters: list[dict] | None = None,
    proxy_url: str | None = None,
) -> dict:
    """Fetches one page of the public tender listing.

    Sorted by `publicDt desc` by default (most recently published to the
    public portal first -- TUNEPS's own "latest" view). Pass
    sort_col="bdRecvEndDt", sort_dir="asc" with an extra `bdRecvEndDt >=` now
    filter for an "open, soonest-deadline-first" view instead (see main.py).
    """
    body = _build_search_body(limit, offset, sort_col, sort_dir, extra_filters or [])
    return await _request_json("POST", LIST_PATH, json_body=body, proxy_url=proxy_url)


async def fetch_bid_detail(bid_id: str, proxy_url: str | None = None) -> dict:
    """Fetches full detail for one tender by its internal `epBidMasterId`.

    Raises RecordNotFound on an invalid/unknown id. Confirmed during recon:
    TUNEPS answers an unknown-but-numeric id with a *200* whose envelope
    carries `code: "420"` and an empty `payload` object rather than a 404 --
    that shape is treated as not-found here too (see CRAWLING_METHOD.md).
    """
    url = DETAIL_PATH.format(bid_id=bid_id)
    body = await _request_json("GET", url, proxy_url=proxy_url)
    payload = body.get("payload") if isinstance(body, dict) else None
    if body.get("code") != "200" or not payload:
        raise RecordNotFound(url)
    return body
