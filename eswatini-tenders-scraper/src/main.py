import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_list_page
from src.constants import LIST_CONFIGS, VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_error_record,
    build_list_record,
    parse_jobbox_page,
    parse_suspended_json,
)
from src.input_errors import input_error


async def run_list(list_type: str, max_results: int, keyword: str, proxy_url_fn) -> list[dict]:
    cfg = LIST_CONFIGS[list_type]
    records: list[dict] = []
    page = 1
    total_available = None
    total_pages = None

    while len(records) < max_results:
        proxy_url = await proxy_url_fn()
        try:
            raw = await fetch_list_page(list_type, page, keyword, proxy_url=proxy_url)
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:{list_type}:page{page}", "blocked_or_transient", repr(e)))
            break

        # Raises UnexpectedShape -- must NOT be swallowed, per project convention.
        parsed = parse_suspended_json(raw) if cfg["kind"] == "json_table" else parse_jobbox_page(raw, list_type)

        total_available = parsed["totalAvailable"]
        total_pages = parsed["totalPages"]

        if not parsed["rows"]:
            break

        for row in parsed["rows"]:
            records.append(build_list_record(list_type, row, total_available, total_pages, page))
            if len(records) >= max_results:
                break

        if cfg["kind"] == "json_table":
            break  # single-call endpoint -- the whole (small) register came back already
        if total_pages is not None and page >= total_pages:
            break
        page += 1

    if total_available is not None and len(records) < total_available and records and "_error" not in records[-1]:
        Actor.log.info(
            f"listType={list_type}: {len(records)} of {total_available} total available rows fetched "
            "(capped by maxResults)."
        )
    return records


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        list_type = input_data.get("listType", "tenders")
        if list_type not in VALID_LIST_TYPES:
            raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")

        max_results = int(input_data.get("maxResults", 50))
        max_results = max(1, min(max_results, 5000))

        keyword = (input_data.get("keyword") or "").strip()

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"listType={list_type} maxResults={max_results} keyword={keyword!r}")
        try:
            records = await run_list(list_type, max_results, keyword, proxy_url_fn)
        except UnexpectedShape:
            raise
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
