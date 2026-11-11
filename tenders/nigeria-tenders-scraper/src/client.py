"""HTTP client wrapper for NOCOPO's public listing and OCDS-download
endpoints.

No login, no CSRF handshake, no API key -- see CRAWLING_METHOD.md. The
listing endpoint (`PublishedRecordHandler.ashx`) is a legacy (pre-1.10)
jQuery DataTables server-side handler that takes classic `sEcho` /
`iDisplayStart` / `iDisplayLength` / `sSearch` params, not the modern
`draw`/`start`/`length` ones (those 500 -- the handler is old code even
though the portal itself is actively updated). The detail endpoint
(`ocdsjson.ashx`) always 302s to a generated `downloads.aspx?file=...zip`
URL and never fails outright even for an unknown ocid -- an invalid ocid
still produces a 200 zip, just one whose single JSON entry is an empty
`{}` (no `releases` key). That case is treated as `RecordNotFound` here,
not retried.
"""

import asyncio
import io
import json
import zipfile

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    DETAIL_ENDPOINT,
    HEADERS,
    LIST_ENDPOINT,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


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


async def fetch_list_page(start: int, length: int, search: str = "", proxy_url: str | None = None) -> dict:
    """One page of NOCOPO's public "Published Records" listing, newest
    DatePublished first (see CRAWLING_METHOD.md for the full param set and
    why the old-style DataTables protocol is required)."""
    params = {
        "sEcho": 1,
        "iDisplayStart": start,
        "iDisplayLength": length,
        "sSearch": search or "",
        "bEscapeRegex": "true",
        "iColumns": 8,
        "iSortingCols": 1,
        "iSortCol_0": 3,  # DatePublished
        "sSortDir_0": "desc",
        "mDataProp_0": "ID",
        "mDataProp_1": "MDA_Code",
        "mDataProp_2": "pi_Project_Title",
        "mDataProp_3": "DatePublished",
        "mDataProp_4": "pi_Package_Number",
        "mDataProp_5": "pi_Lot_Number",
        "mDataProp_6": "pb_BudgetYear",
        "mDataProp_7": "MDA_Code",
    }
    r = await _get(LIST_ENDPOINT, params, proxy_url=proxy_url)
    try:
        return r.json()
    except ValueError as e:
        raise FetchFailed(f"list page start={start} returned non-JSON body: {e!r}") from e


async def fetch_record_detail(ocid: str, proxy_url: str | None = None) -> dict:
    """Downloads and unzips the single-OCID OCDS release package NOCOPO's
    own "Download" link fetches for one row. Raises RecordNotFound for an
    unknown/invalid ocid (still a 200, but with an empty '{}' payload)."""
    r = await _get(DETAIL_ENDPOINT, {"d": 1, "ocid": ocid}, proxy_url=proxy_url)

    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            raw = zf.read(names[0]) if names else b""
    except zipfile.BadZipFile as e:
        raise FetchFailed(f"detail ocid={ocid!r} did not return a valid zip ({len(r.content)} bytes): {e!r}") from e

    if not raw.strip():
        raise RecordNotFound(ocid)

    try:
        data = json.loads(raw)
    except ValueError as e:
        raise FetchFailed(f"detail ocid={ocid!r} zip entry was not valid JSON: {e!r}") from e

    if not isinstance(data, dict) or not data.get("releases"):
        raise RecordNotFound(ocid)
    return data
