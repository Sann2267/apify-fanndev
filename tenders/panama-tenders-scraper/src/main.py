import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import PanamaComprasClient
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP
from src.extractor import (
    UnexpectedShape,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_record_detail,
    parse_records_page,
)
from src.input_errors import input_error


async def run_list(input_data: dict, proxy_url_fn) -> list[dict]:
    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 500))
    start_cursor = str(input_data.get("startCursor") or "").strip() or None

    filters_used = {"startCursor": start_cursor}

    proxy_url = await proxy_url_fn()
    client = PanamaComprasClient(proxy_url)
    records: list[dict] = []
    next_url = start_cursor
    pages_fetched = 0
    try:
        while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
            data = await client.fetch_records_page(next_url)
            page_records, next_url = parse_records_page(data)  # raises UnexpectedShape -- not swallowed
            pages_fetched += 1
            if not page_records:
                break  # legitimate "no more results at this cursor"
            records.extend(page_records)
            if not next_url or len(records) >= max_results:
                break
            await asyncio.sleep(LIST_PAGE_DELAY)
    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix. Keep whatever records were already
        # collected before the failure rather than discarding a partial run.
        await client.close()
        result = [build_list_record(r, filters_used) for r in records[:max_results]]
        partial_note = f"; {len(records)} record(s) already collected before this failure" if records else ""
        result.append(build_error_record(filters_used, "blocked_or_transient", f"{e!r}{partial_note}"))
        return result
    finally:
        await client.close()

    if not records:
        return [build_error_record(filters_used, "not_found", "feed returned zero records at this cursor")]

    result = [build_list_record(r, filters_used) for r in records[:max_results]]
    # The upstream feed has no server-side date/keyword filtering (see
    # constants.py) -- pagination is the only way to see more of it. Surface
    # the next cursor on the last record so a future run's 'startCursor'
    # input can continue exactly where this run stopped, instead of always
    # re-fetching the same first page.
    if next_url and len(records) >= max_results:
        result[-1]["_nextCursor"] = next_url
    return result


async def run_detail(ocids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(ocids)

    async def _one(i: int, ocid: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            client = PanamaComprasClient(proxy_url)
            try:
                data = await client.fetch_record(ocid)
                if data is None:
                    results[i] = build_error_record(ocid, "not_found", "no tender found for this ocid")
                    return
                compiled = parse_record_detail(data, ocid)  # raises UnexpectedShape -- not swallowed
                results[i] = build_detail_record(ocid, compiled)
            except (RuntimeError, RequestException, ConnectionError) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from
                # the builtin one (parallel MRO, same name) -- both listed.
                results[i] = build_error_record(ocid, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, ocid) for i, ocid in enumerate(ocids)))
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
            Actor.log.info(
                f"mode=list maxResults={input_data.get('maxResults', 50)} "
                f"startCursor={'set' if input_data.get('startCursor') else 'none'}"
            )
            records = await run_list(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ocids = []
        if input_data.get("ocid"):
            raw_ocids.append(input_data["ocid"])
        raw_ocids.extend(input_data.get("ocids") or [])
        ocids = []
        seen = set()
        for raw in raw_ocids:
            ocid = str(raw).strip()
            if ocid and ocid not in seen:
                seen.add(ocid)
                ocids.append(ocid)
        if not ocids:
            raise input_error(
                "Provide 'ocid' or a non-empty 'ocids' array -- an OCDS ocid "
                "(e.g. the 'ocid' field from a 'list' mode run)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))

        Actor.log.info(f"mode=detail {len(ocids)} ocid(s), maxConcurrency={max_concurrency}")
        records = await run_detail(ocids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
