"""HTTP client wrapper for VNEPS's internal search/detail JSON services.

No login, no CSRF handshake, no API key -- every call here is a plain POST
that returns JSON directly (see CRAWLING_METHOD.md). The one real quirk is
the `?token=` query param both endpoints require: it's meant to be a Google
reCAPTCHA v3 token, but the server never actually verifies it -- any
non-empty placeholder string works identically to a real one.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    DETAIL_RESULT_PATH,
    HEADERS,
    MAX_RETRIES,
    RECAPTCHA_TOKEN_PLACEHOLDER,
    RETRY_DELAY_BASE,
    SEARCH_PATH,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A POST never produced a usable 200 response after retries."""


class RecordNotFound(Exception):
    """A detail lookup came back with a null DTO -- genuinely no such record."""


async def _post_json(url: str, body, proxy_url: str | None = None):
    """Runs a single POST with retries. Returns the parsed JSON body.

    Raises FetchFailed if every retry is exhausted on a non-200 status, an
    empty body, or a connection-level error.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.post(url, json=body, headers=HEADERS)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"POST {url} returned {r.status_code} ({len(r.content)} bytes)")
            return r.json()
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


def _with_token(path: str) -> str:
    return f"{path}?token={RECAPTCHA_TOKEN_PLACEHOLDER}"


async def search_records(
    *,
    keyword: str,
    match_fields: list[str],
    filters: list[dict],
    page_number: int,
    page_size: int,
    proxy_url: str | None = None,
) -> dict | None:
    """Runs one page of the "contractor selection" smart search.

    Returns the parsed `{"page": {...}, "agg": {...}}` body, or None once
    the server reports `{"page": null}` -- which it does instead of erroring
    once `page_number * page_size` runs past this particular filtered
    query's result window (see constants.py / CRAWLING_METHOD.md), i.e. the
    honest "no more results" signal for this endpoint.
    """
    from src.constants import SEARCH_INDEX

    body = [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": SEARCH_INDEX,
                    "keyWord": keyword,
                    "matchType": "all-1",
                    "matchFields": match_fields,
                    "filters": filters,
                }
            ],
        }
    ]
    data = await _post_json(_with_token(SEARCH_PATH), body, proxy_url=proxy_url)
    if not isinstance(data, dict) or data.get("page") is None:
        return None
    return data


async def fetch_contractor_result_detail(input_result_id: str, proxy_url: str | None = None) -> dict:
    """Fetches the full contractor-selection-result detail (award/contract
    detail: winning bidder, price, decision documents, lot-by-lot results)
    for one `inputResultId`.

    Raises RecordNotFound when the id is well-formed but doesn't match any
    record -- the server responds 200 with a null DTO in that case rather
    than a 404.
    """
    data = await _post_json(_with_token(DETAIL_RESULT_PATH), {"id": input_result_id}, proxy_url=proxy_url)
    if not isinstance(data, dict) or not data.get("bideContractorInputResultDTO"):
        raise RecordNotFound(input_result_id)
    return data
