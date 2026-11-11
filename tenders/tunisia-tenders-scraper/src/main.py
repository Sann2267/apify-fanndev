import asyncio
from datetime import datetime, timezone

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_bid_detail, fetch_list_page
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP, RESULTS_PER_PAGE
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


def _now_sql() -> str:
    """TUNEPS's bdRecvEndDt filter compares against a plain SQL-style
    timestamp string, not ISO 8601 -- see CRAWLING_METHOD.md."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def run_list(open_only: bool, keyword: str | None, max_results: int, proxy_url_fn) -> list[dict]:
    """Pages through TUNEPS's public tender listing.

    Default view sorts by `publicDt desc` -- most recently published to the
    public portal first, TUNEPS's own "latest" ordering. `open_only=True`
    instead filters to tenders whose submission deadline (`bdRecvEndDt`)
    hasn't passed yet and sorts by soonest-deadline-first.
    """
    extra_filters = []
    if open_only:
        extra_filters.append({"key": "bdRecvEndDt", "value": _now_sql(), "specificSearch": ">="})
    if keyword:
        extra_filters.append({"key": "bidNmFr", "value": keyword, "specificSearch": "upper_like"})

    sort_col, sort_dir = ("bdRecvEndDt", "asc") if open_only else ("publicDt", "desc nulls last")
    context = f"list:openOnly={open_only},keyword={keyword!r}"

    records: list[dict] = []
    seen_ids: set = set()
    offset = 0
    pages_fetched = 0

    while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
        limit = min(RESULTS_PER_PAGE, max_results - len(records))
        proxy_url = await proxy_url_fn()
        try:
            page = await fetch_list_page(
                limit,
                offset,
                sort_col=sort_col,
                sort_dir=sort_dir,
                extra_filters=extra_filters,
                proxy_url=proxy_url,
            )
        except TRANSIENT_EXC as e:
            records.append(build_error_record(f"{context},offset={offset}", "blocked_or_transient", repr(e)))
            break

        pages_fetched += 1
        payload = page.get("payload") if isinstance(page, dict) else None
        items = (payload or {}).get("data")
        if not items:
            Actor.log.info(f"list: no more records at offset={offset} -- reached the end of the result set.")
            break

        new_this_page = 0
        for item in items:
            bid_id = item.get("epBidMasterId") if isinstance(item, dict) else None
            if bid_id is not None and bid_id in seen_ids:
                continue
            if bid_id is not None:
                seen_ids.add(bid_id)
            records.append(build_list_record(item, context))  # raises UnexpectedShape -- not swallowed
            new_this_page += 1
            if len(records) >= max_results:
                break

        if new_this_page == 0:
            # Every id on this page was already seen -- the result set shifted
            # under us (new tenders published mid-run) rather than genuinely
            # ending. Stop rather than looping forever re-fetching the same page.
            Actor.log.info(f"list: page at offset={offset} returned only already-seen records -- stopping.")
            break

        if len(items) < limit:
            break  # short page -- genuinely the last one

        offset += limit
        if len(records) < max_results:
            await asyncio.sleep(LIST_PAGE_DELAY)

    if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
        Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")

    return records


async def run_detail(bid_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(bid_ids)

    async def _one(i: int, bid_id: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                body = await fetch_bid_detail(bid_id, proxy_url=proxy_url)
            except RecordNotFound:
                results[i] = build_error_record(bid_id, "not_found", "no tender exists for this bid id")
                return
            except TRANSIENT_EXC as e:
                results[i] = build_error_record(bid_id, "blocked_or_transient", repr(e))
                return
            results[i] = build_detail_record(bid_id, body)  # raises UnexpectedShape -- not swallowed

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
            open_only = bool(input_data.get("openOnly", False))
            keyword = (input_data.get("keyword") or "").strip() or None
            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, 10000))

            Actor.log.info(f"mode=list openOnly={open_only} keyword={keyword!r} maxResults={max_results}")
            records = await run_list(open_only, keyword, max_results, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("bidId") not in (None, ""):
            raw_ids.append(input_data["bidId"])
        raw_ids.extend(input_data.get("bidIds") or [])
        bid_ids = []
        seen = set()
        for raw in raw_ids:
            bid_id = str(raw).strip()
            if bid_id and bid_id not in seen:
                seen.add(bid_id)
                bid_ids.append(bid_id)
        if not bid_ids:
            raise input_error(
                "Provide 'bidId' or a non-empty 'bidIds' array (TUNEPS internal epBidMasterId values)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(bid_ids)} bidId(s), maxConcurrency={max_concurrency}")
        records = await run_detail(bid_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
