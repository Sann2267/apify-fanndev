import asyncio
import datetime

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_record, fetch_search_page
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP, MIN_SEARCH_LEN, MIN_YEAR
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error


async def _enrich_with_detail(ocid: str, proxy_url_fn) -> dict:
    """Best-effort enrichment for list mode -- never raises. Adds the merged
    OCDS summary fields onto a list row, or '_detailError' if the detail
    fetch itself failed."""
    proxy_url = await proxy_url_fn()
    try:
        data = await fetch_record(ocid, proxy_url=proxy_url)
    except RecordNotFound:
        return {"_detailError": "not_found"}
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return {"_detailError": repr(e)}
    detail = build_detail_record(ocid, data)  # raises UnexpectedShape -- not swallowed
    detail.pop("_input", None)
    detail.pop("_source", None)
    detail.pop("_scrapedAt", None)
    return detail


async def run_list(
    year: int,
    search: str,
    max_results: int,
    buyer: str,
    supplier: str,
    fetch_detail: bool,
    proxy_url_fn,
) -> list[dict]:
    records: list[dict] = []
    page = 1
    pages_fetched = 0

    while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
        proxy_url = await proxy_url_fn()
        try:
            result = await fetch_search_page(year, search, page, buyer=buyer, supplier=supplier, proxy_url=proxy_url)
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:year={year}:search={search}:page={page}", "blocked_or_transient", repr(e)))
            break

        pages_fetched += 1
        rows = result.get("data") if isinstance(result, dict) else None
        if not rows:
            Actor.log.info(f"list: no more rows at page={page} -- reached the end of the result set.")
            break

        for row in rows:
            rec = build_list_record(row, year, search)  # raises UnexpectedShape -- not swallowed
            if fetch_detail and rec.get("ocid"):
                rec.update(await _enrich_with_detail(rec["ocid"], proxy_url_fn))
            records.append(rec)
            if len(records) >= max_results:
                break

        total_pages = result.get("pages") if isinstance(result, dict) else None
        if isinstance(total_pages, int) and page >= total_pages:
            Actor.log.info(f"list: reached upstream's last page ({total_pages}).")
            break

        page += 1
        if len(records) < max_results:
            await asyncio.sleep(LIST_PAGE_DELAY)

    if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
        Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")

    return records


async def run_detail(ocids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(ocids)

    async def _one(i: int, ocid: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                data = await fetch_record(ocid, proxy_url=proxy_url)
            except RecordNotFound:
                results[i] = build_error_record(ocid, "not_found", "no record exists for this ocid")
                return
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(ocid, "blocked_or_transient", repr(e))
                return
            results[i] = build_detail_record(ocid, data)  # raises UnexpectedShape -- not swallowed

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
            search = str(input_data.get("searchQuery") or "").strip()
            if len(search) < MIN_SEARCH_LEN:
                raise input_error(
                    f"searchQuery is required for mode=list and must be at least {MIN_SEARCH_LEN} "
                    f"characters -- SERCOP's own search_ocds API has no 'browse everything' call "
                    f"(see CRAWLING_METHOD.md). Got: {search!r}"
                )

            current_year = datetime.datetime.now(datetime.timezone.utc).year
            year = int(input_data.get("year") or current_year)
            if not (MIN_YEAR <= year <= current_year):
                raise input_error(f"year must be between {MIN_YEAR} and {current_year}, got {year}")

            buyer = str(input_data.get("buyer") or "").strip()
            supplier = str(input_data.get("supplier") or "").strip()
            max_results = int(input_data.get("maxResults", 25))
            max_results = max(1, min(max_results, 2000))
            fetch_detail = bool(input_data.get("fetchDetail", False))

            Actor.log.info(
                f"mode=list year={year} search={search!r} buyer={buyer!r} supplier={supplier!r} "
                f"maxResults={max_results} fetchDetail={fetch_detail}"
            )
            records = await run_list(year, search, max_results, buyer, supplier, fetch_detail, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("ocid"):
            raw_ids.append(input_data["ocid"])
        raw_ids.extend(input_data.get("ocids") or [])
        ocids = []
        seen = set()
        for raw in raw_ids:
            ocid = str(raw).strip()
            if ocid and ocid not in seen:
                seen.add(ocid)
                ocids.append(ocid)
        if not ocids:
            raise input_error(
                "Provide 'ocid' or a non-empty 'ocids' array (SERCOP OCIDs, "
                "e.g. from a 'list' mode run's ocid field)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(ocids)} ocid(s), maxConcurrency={max_concurrency}")
        records = await run_detail(ocids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
