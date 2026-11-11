import asyncio
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_detail_page, fetch_list_page
from src.constants import LIST_CONFIGS, VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_detail_page,
    parse_list_page,
)
from src.input_errors import input_error

BID_ID_IN_URL_RE = re.compile(r"/index/bid/(\d+)")


def _normalize_bid_id(value) -> str | None:
    """Accepts a bare numeric id (str/int) or a full bid URL and returns the
    numeric id as a string, or None if nothing usable was found."""
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return s
    m = BID_ID_IN_URL_RE.search(s)
    return m.group(1) if m else None


async def run_list(list_type: str, max_results: int, proxy_url_fn) -> list[dict]:
    cfg = LIST_CONFIGS[list_type]
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_list_page(cfg["path"], proxy_url=proxy_url)
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return [build_error_record(f"list:{list_type}", "blocked_or_transient", repr(e))]

    parsed = parse_list_page(html_text, list_type)  # raises UnexpectedShape -- must NOT be swallowed
    total_available = len(parsed["rows"])
    rows = parsed["rows"][:max_results]

    if total_available > len(rows):
        Actor.log.info(
            f"listType={list_type}: {len(rows)} of {total_available} total available rows kept "
            "(capped by maxResults)."
        )
    return [build_list_record(list_type, row, total_available) for row in rows]


async def run_detail(bid_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(bid_ids)

    async def _one(i: int, bid_id: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                html_text = await fetch_detail_page(bid_id, proxy_url=proxy_url)
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(bid_id, "blocked_or_transient", repr(e))
                return
            parsed = parse_detail_page(html_text)  # raises UnexpectedShape -- fail loud, not swallowed
            results[i] = build_detail_record(bid_id, parsed)

    await asyncio.gather(*(_one(i, bid_id) for i, bid_id in enumerate(bid_ids)))
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
            list_type = input_data.get("listType", "all")
            if list_type not in VALID_LIST_TYPES:
                raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")
            max_results = int(input_data.get("maxResults", 100))
            max_results = max(1, min(max_results, 2000))

            Actor.log.info(f"mode=list listType={list_type} maxResults={max_results}")
            records = await run_list(list_type, max_results, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("bidId"):
            raw_ids.append(input_data["bidId"])
        raw_ids.extend(input_data.get("bidIds") or [])
        bid_ids = []
        seen = set()
        for raw in raw_ids:
            bid_id = _normalize_bid_id(raw)
            if bid_id and bid_id not in seen:
                seen.add(bid_id)
                bid_ids.append(bid_id)
        if not bid_ids:
            raise input_error("Provide 'bidId' or a non-empty 'bidIds' array (numeric IDs or bid URLs).")

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(bid_ids)} bidId(s), maxConcurrency={max_concurrency}")
        records = await run_detail(bid_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
