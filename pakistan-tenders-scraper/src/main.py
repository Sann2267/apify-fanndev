import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, PpraClient
from src.constants import (
    ACTIVE_TENDERS_URL,
    PROCUREMENT_CATEGORY_MAP,
    SECTOR_MAP,
    STATUS_MAP,
    TENDER_NATURE_MAP,
    TENDER_TYPE_MAP,
    TENDERS_HISTORY_URL,
)
from src.extractor import (
    TENDER_NO_IN_URL_RE,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_detail,
    parse_listing,
)
from src.input_errors import input_error


def _normalize_tender_no(value) -> str | None:
    """Accepts a bare tender number (e.g. TS0000012236E) or a full detail
    URL and returns the bare tender number, or None if nothing usable was
    found."""
    s = str(value).strip()
    if not s:
        return None
    if "/" not in s:
        return s
    m = TENDER_NO_IN_URL_RE.search(s)
    return m.group(1) if m else None


def _build_params(input_data: dict) -> tuple[dict, list[str]]:
    """Returns (query_params, label_parts) -- only non-default filters are
    included in either, so an unfiltered run's query_label reads 'latest'."""
    params: dict = {}
    label_parts: list[str] = []

    def _map_field(input_key: str, query_key: str, value_map: dict, label: str):
        raw = input_data.get(input_key) or "all"
        if raw not in value_map:
            raise ValueError(f"{input_key} must be one of {list(value_map)}, got {raw!r}")
        if raw != "all":
            params[query_key] = value_map[raw]
            label_parts.append(f"{label}={raw}")

    keyword = (input_data.get("keyword") or "").strip()
    if keyword:
        params["keyword"] = keyword
        label_parts.append(f"keyword={keyword!r}")

    tender_no = (input_data.get("tenderNoFilter") or "").strip()
    if tender_no:
        params["tender_no"] = tender_no
        label_parts.append(f"tenderNoFilter={tender_no!r}")

    _map_field("procurementCategory", "procurement_category", PROCUREMENT_CATEGORY_MAP, "category")
    _map_field("tenderType", "tender_type", TENDER_TYPE_MAP, "type")
    _map_field("sector", "sector", SECTOR_MAP, "sector")
    _map_field("tenderNature", "tender_nature", TENDER_NATURE_MAP, "nature")
    _map_field("status", "status", STATUS_MAP, "status")

    organization_id = (input_data.get("organizationId") or "").strip()
    if organization_id:
        params["organization"] = organization_id
        label_parts.append(f"organizationId={organization_id!r}")

    country_id = (input_data.get("countryId") or "").strip()
    if country_id:
        params["country"] = country_id
        label_parts.append(f"countryId={country_id!r}")

    for input_key, query_key in (
        ("advertiseDateFrom", "advertise_date_from"),
        ("advertiseDateTo", "advertise_date_to"),
        ("closingDate", "closing_date"),
    ):
        value = (input_data.get(input_key) or "").strip()
        if value:
            params[query_key] = value
            label_parts.append(f"{input_key}={value!r}")

    return params, label_parts


async def run_list(input_data: dict, proxy_url_fn) -> list[dict]:
    listing_type = input_data.get("listingType") or "active"
    if listing_type not in ("active", "history"):
        raise ValueError(f"listingType must be 'active' or 'history', got {listing_type!r}")
    base_url = ACTIVE_TENDERS_URL if listing_type == "active" else TENDERS_HISTORY_URL

    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 2000))
    start_page = max(1, int(input_data.get("startPage", 1)))

    params, label_parts = _build_params(input_data)
    query_label = "latest" if not label_parts else "search:" + ",".join(label_parts)

    proxy_url = await proxy_url_fn()
    client = PpraClient(proxy_url)
    try:
        collected: list[dict] = []
        page = start_page
        while len(collected) < max_results:
            page_params = {**params, "page": page}
            html_text = await client.fetch_listing(base_url, page_params)
            parsed = parse_listing(html_text)  # raises UnexpectedShape -- must NOT be swallowed
            if not parsed["rows"]:
                Actor.log.info(f"{query_label} ({listing_type}): page {page} returned 0 rows -- stopping.")
                break
            for row in parsed["rows"]:
                collected.append(build_list_record(row, listing_type, page, query_label))
            Actor.log.info(
                f"{query_label} ({listing_type}): page {page} -> {len(parsed['rows'])} row(s), "
                f"{len(collected)} collected so far."
            )
            if not parsed["hasNextPage"]:
                break
            page += 1
        if len(collected) > max_results:
            collected = collected[:max_results]
        if not collected:
            Actor.log.info(f"{query_label} ({listing_type}): matched 0 tenders.")
        return collected
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError/RequestException does not
        # inherit from Python's builtin ConnectionError -- both listed, per
        # this portfolio's Babak 22b fix.
        return [build_error_record(query_label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail(tender_nos: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(tender_nos)

    async def _one(i: int, tender_no: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            client = PpraClient(proxy_url)
            try:
                html_text = await client.fetch_detail(tender_no)
                parsed = parse_detail(html_text)  # raises UnexpectedShape -- fail loud, not swallowed
                results[i] = build_detail_record(tender_no, parsed)
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                results[i] = build_error_record(tender_no, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, tno) for i, tno in enumerate(tender_nos)))
    return [r for r in results if r is not None]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "list")
        if mode not in ("list", "detail"):
            raise input_error(f"mode must be 'list' or 'detail', got {mode!r}")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "list":
            Actor.log.info("mode=list")
            records = await run_list(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_nos = []
        if input_data.get("tenderNo"):
            raw_nos.append(input_data["tenderNo"])
        raw_nos.extend(input_data.get("tenderNos") or [])
        tender_nos = []
        seen = set()
        for raw in raw_nos:
            tno = _normalize_tender_no(raw)
            if tno and tno not in seen:
                seen.add(tno)
                tender_nos.append(tno)
        if not tender_nos:
            raise input_error("Provide 'tenderNo' or a non-empty 'tenderNos' array (tender numbers or detail URLs).")

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        max_concurrency = max(1, min(max_concurrency, 10))

        Actor.log.info(f"mode=detail {len(tender_nos)} tenderNo(s), maxConcurrency={max_concurrency}")
        records = await run_detail(tender_nos, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
