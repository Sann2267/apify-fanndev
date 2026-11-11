import asyncio
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, NotFoundOrRestricted, fetch_detail_page, fetch_list_page
from src.constants import LIST_CONFIGS, VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_detail_record,
    build_error_record,
    build_list_record,
    find_category_total,
    find_last_page_seen,
    parse_detail_page,
    parse_list_page,
)
from src.input_errors import input_error

RESOURCE_LINK_RE = re.compile(r"type_publication=([A-Za-z-]+)&id_publication=(\d+)")
RESOURCE_PAIR_RE = re.compile(r"^\s*([A-Za-z-]+)\s*[:_]\s*(\d+)\s*$")


def _normalize_resource(value) -> tuple[str, str] | None:
    """Accepts a full detail URL (.../details?type_publication=X&id_publication=Y)
    or a bare "TYPE:ID" / "TYPE_ID" pair (e.g. "AO:64638"), and returns
    (type_publication, id_publication), or None if nothing usable was found."""
    s = str(value).strip()
    if not s:
        return None
    m = RESOURCE_LINK_RE.search(s)
    if m:
        return m.group(1), m.group(2)
    m = RESOURCE_PAIR_RE.match(s)
    if m:
        return m.group(1), m.group(2)
    return None


async def run_list(list_type: str, max_results: int, proxy_url_fn) -> list[dict]:
    cfg = LIST_CONFIGS[list_type]
    records: list[dict] = []
    page = 1
    total_available = None
    last_page_seen = None

    while len(records) < max_results:
        proxy_url = await proxy_url_fn()
        try:
            html_text = await fetch_list_page(cfg["path"], cfg["query"], page, proxy_url=proxy_url)
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:{list_type}:page{page}", "blocked_or_transient", repr(e)))
            break

        parsed = parse_list_page(html_text)  # raises UnexpectedShape -- must NOT be swallowed, per project convention
        if page == 1:
            total_available = find_category_total(html_text, cfg["val"])
        last_page_seen = find_last_page_seen(html_text) or last_page_seen

        if not parsed["rows"]:
            break

        for row in parsed["rows"]:
            records.append(build_list_record(list_type, row, total_available, last_page_seen, page))
            if len(records) >= max_results:
                break

        if last_page_seen is not None and page >= last_page_seen:
            break
        page += 1

    if total_available is not None and len(records) < total_available and records and "_error" not in records[-1]:
        Actor.log.info(
            f"listType={list_type}: {len(records)} of {total_available} total available rows fetched "
            "(capped by maxResults)."
        )
    return records


async def run_detail(resource_pairs: list[tuple[str, str]], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(resource_pairs)

    async def _one(i: int, pair: tuple[str, str]):
        type_publication, id_publication = pair
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                html_text = await fetch_detail_page(type_publication, id_publication, proxy_url=proxy_url)
            except NotFoundOrRestricted as e:
                results[i] = build_error_record(f"{type_publication}:{id_publication}", "not_found_or_restricted", repr(e))
                return
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(f"{type_publication}:{id_publication}", "blocked_or_transient", repr(e))
                return
            parsed = parse_detail_page(html_text)  # raises UnexpectedShape -- fail loud, not swallowed
            results[i] = build_detail_record(type_publication, id_publication, parsed)

    await asyncio.gather(*(_one(i, pair) for i, pair in enumerate(resource_pairs)))
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
            list_type = input_data.get("listType", "latest")
            if list_type not in VALID_LIST_TYPES:
                raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")
            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, 5000))

            Actor.log.info(f"mode=list listType={list_type} maxResults={max_results}")
            records = await run_list(list_type, max_results, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("resourceId"):
            raw_ids.append(input_data["resourceId"])
        raw_ids.extend(input_data.get("resourceIds") or [])
        resource_pairs: list[tuple[str, str]] = []
        seen = set()
        for raw in raw_ids:
            pair = _normalize_resource(raw)
            if pair and pair not in seen:
                seen.add(pair)
                resource_pairs.append(pair)
        if not resource_pairs:
            raise input_error(
                "Provide 'resourceId' or a non-empty 'resourceIds' array "
                "(each a full armp.cm detail URL, or a 'TYPE:ID' pair like 'AO:64638')."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(resource_pairs)} resource(s), maxConcurrency={max_concurrency}")
        records = await run_detail(resource_pairs, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
