import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_contractor_result_detail, search_records
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP, MAX_PAGE_SIZE, MAX_RESULT_WINDOW
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error

MATCH_FIELDS = ["notifyNo", "bidName"]


def _build_filters(date_from: str | None, date_to: str | None, record_type: str | None) -> list[dict]:
    filters: list[dict] = []
    if date_from or date_to:
        filters.append({"fieldName": "publicDate", "searchType": "range", "from": date_from, "to": date_to})
    if record_type and record_type != "all":
        filters.append({"fieldName": "type", "searchType": "in", "fieldValues": [record_type]})
    return filters


async def run_list(
    keyword: str,
    date_from: str | None,
    date_to: str | None,
    record_type: str,
    max_results: int,
    proxy_url_fn,
) -> list[dict]:
    """Pages through the "contractor selection" smart-search index, newest
    `publicDate` first (the server's own default sort -- see
    CRAWLING_METHOD.md).

    A given filtered query only exposes its first `MAX_RESULT_WINDOW`
    (10000) hits -- the server signals the end of that window with
    `{"page": null}` (200 OK) rather than an error, which this actor treats
    as an honest "no more results for this query" stop condition, not a
    failure. Narrowing `date_from`/`date_to` gives a fresh 10000-record
    window for that slice, for anyone who needs to look further back.
    """
    filters = _build_filters(date_from, date_to, record_type)
    context = f"list:keyword={keyword!r} dateFrom={date_from!r} dateTo={date_to!r} recordType={record_type!r}"
    records: list[dict] = []
    page_number = 0
    pages_fetched = 0

    while (
        len(records) < max_results
        and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP
        and page_number * MAX_PAGE_SIZE < MAX_RESULT_WINDOW
    ):
        proxy_url = await proxy_url_fn()
        try:
            result = await search_records(
                keyword=keyword,
                match_fields=MATCH_FIELDS,
                filters=filters,
                page_number=page_number,
                page_size=MAX_PAGE_SIZE,
                proxy_url=proxy_url,
            )
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"{context} page={page_number}", "blocked_or_transient", repr(e)))
            break

        pages_fetched += 1
        if result is None:
            Actor.log.info(
                f"list: server returned page=null at pageNumber={page_number} -- "
                "reached the end of this query's result window."
            )
            break

        content = result.get("page", {}).get("content") or []
        if not content:
            Actor.log.info(f"list: empty content at pageNumber={page_number} -- stopping.")
            break

        for hit in content:
            records.append(build_list_record(hit, context))  # raises UnexpectedShape -- not swallowed
            if len(records) >= max_results:
                break

        page_number += 1
        if len(records) < max_results:
            await asyncio.sleep(LIST_PAGE_DELAY)

    if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
        Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")

    return records


async def run_detail(input_result_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(input_result_ids)

    async def _one(i: int, input_result_id: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                data = await fetch_contractor_result_detail(input_result_id, proxy_url=proxy_url)
            except RecordNotFound:
                results[i] = build_error_record(
                    input_result_id, "not_found", "no contractor-selection-result record exists for this id"
                )
                return
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(input_result_id, "blocked_or_transient", repr(e))
                return
            results[i] = build_detail_record(input_result_id, data)  # raises UnexpectedShape -- not swallowed

    await asyncio.gather(*(_one(i, rid) for i, rid in enumerate(input_result_ids)))
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
            keyword = str(input_data.get("keyword") or "")
            date_from = input_data.get("dateFrom") or None
            date_to = input_data.get("dateTo") or None
            record_type = input_data.get("recordType") or "all"
            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, MAX_RESULT_WINDOW))

            Actor.log.info(
                f"mode=list keyword={keyword!r} dateFrom={date_from!r} dateTo={date_to!r} "
                f"recordType={record_type!r} maxResults={max_results}"
            )
            records = await run_list(keyword, date_from, date_to, record_type, max_results, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("inputResultId"):
            raw_ids.append(input_data["inputResultId"])
        raw_ids.extend(input_data.get("inputResultIds") or [])
        input_result_ids = []
        seen = set()
        for raw in raw_ids:
            rid = str(raw).strip()
            if rid and rid not in seen:
                seen.add(rid)
                input_result_ids.append(rid)
        if not input_result_ids:
            raise input_error(
                "Provide 'inputResultId' or a non-empty 'inputResultIds' array "
                "(VNEPS contractor-selection-result ids, found on 'list' mode "
                "records that reached the award stage -- their 'inputResultId' field)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(input_result_ids)} id(s), maxConcurrency={max_concurrency}")
        records = await run_detail(input_result_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
