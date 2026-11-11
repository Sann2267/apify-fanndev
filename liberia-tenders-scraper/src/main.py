import asyncio
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_detail_page, fetch_list_page
from src.constants import LIST_CONFIGS, RESULTS_PER_PAGE, VALID_LIST_TYPES
from src.extractor import (
    LIST_PARSERS,
    UnexpectedShape,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_detail_page,
)
from src.input_errors import input_error

RESOURCE_ID_IN_URL_RE = re.compile(r"resourceId=(\d+)")


def _normalize_resource_id(value) -> str | None:
    """Accepts a bare numeric id (str/int) or a full tender URL and returns
    the numeric id as a string, or None if nothing usable was found."""
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return s
    m = RESOURCE_ID_IN_URL_RE.search(s)
    return m.group(1) if m else None


async def run_list(list_type: str, max_results: int, proxy_url_fn) -> list[dict]:
    cfg = LIST_CONFIGS[list_type]
    parser = LIST_PARSERS[list_type]
    records: list[dict] = []
    page = 1
    widget_id = None
    total_available = None

    while len(records) < max_results:
        proxy_url = await proxy_url_fn()
        try:
            html_text = await fetch_list_page(cfg["path"], cfg["query"], page, widget_id, proxy_url=proxy_url)
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:{list_type}:page{page}", "blocked_or_transient", repr(e)))
            break

        parsed = parser(html_text)  # raises UnexpectedShape -- must NOT be swallowed, per project convention
        total_available = parsed["totalAvailable"]
        if page == 1:
            widget_id = parsed["widgetId"]

        if not parsed["rows"]:
            break

        for row in parsed["rows"]:
            records.append(build_list_record(list_type, row, total_available, page))
            if len(records) >= max_results:
                break

        max_pages_available = (total_available + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE if total_available else page
        if page >= max_pages_available:
            break
        page += 1

    if total_available is not None and len(records) < total_available and records and "_error" not in records[-1]:
        Actor.log.info(
            f"listType={list_type}: {len(records)} of {total_available} total available rows fetched "
            "(capped by maxResults)."
        )
    return records


async def run_detail(resource_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(resource_ids)

    async def _one(i: int, rid: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                html_text, final_url = await fetch_detail_page(rid, proxy_url=proxy_url)
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(rid, "blocked_or_transient", repr(e))
                return
            parsed = parse_detail_page(html_text, final_url)  # raises UnexpectedShape -- fail loud, not swallowed
            results[i] = build_detail_record(rid, parsed)

    await asyncio.gather(*(_one(i, rid) for i, rid in enumerate(resource_ids)))
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
            list_type = input_data.get("listType", "current")
            if list_type not in VALID_LIST_TYPES:
                raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")
            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, 5000))

            Actor.log.info(f"mode=list listType={list_type} maxResults={max_results}")
            try:
                records = await run_list(list_type, max_results, proxy_url_fn)
            except UnexpectedShape:
                raise
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("resourceId"):
            raw_ids.append(input_data["resourceId"])
        raw_ids.extend(input_data.get("resourceIds") or [])
        resource_ids = []
        seen = set()
        for raw in raw_ids:
            rid = _normalize_resource_id(raw)
            if rid and rid not in seen:
                seen.add(rid)
                resource_ids.append(rid)
        if not resource_ids:
            raise input_error("Provide 'resourceId' or a non-empty 'resourceIds' array (numeric IDs or tender URLs).")

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(resource_ids)} resourceId(s), maxConcurrency={max_concurrency}")
        records = await run_detail(resource_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
