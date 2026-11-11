import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_record, fetch_release_by_url, fetch_rss
from src.constants import DETAIL_LINK_DELAY, MAX_LIST_RESULTS, MIN_YEAR
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error

# Errors that mean "this GET never produced a usable response" -- retried
# internally by client.py, and still raised after retries are exhausted here.
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b
# fix.
TRANSIENT_ERRORS = (FetchFailed, RuntimeError, ConnectionError, RequestException)


async def _fetch_full_detail(id_compra: int, proxy_url_fn) -> dict:
    """Fetches the record for one id_compra, follows every linked release,
    and folds them into one detail record. Raises RecordNotFound /
    TRANSIENT_ERRORS / UnexpectedShape -- never swallows."""
    proxy_url = await proxy_url_fn()
    data = await fetch_record(id_compra, proxy_url=proxy_url)
    link_refs = data["records"][0].get("releases") or []

    full_releases = []
    for ref in link_refs:
        url = (ref or {}).get("url")
        if not url:
            continue
        proxy_url = await proxy_url_fn()
        release_data = await fetch_release_by_url(url, proxy_url=proxy_url)
        full_releases.extend(release_data.get("releases") or [])
        if len(link_refs) > 1:
            await asyncio.sleep(DETAIL_LINK_DELAY)

    return build_detail_record(id_compra, link_refs, full_releases)


async def _enrich_with_detail(id_compra: int, proxy_url_fn) -> dict:
    """Best-effort enrichment for list mode -- never raises. Adds the merged
    record summary fields onto a list row, or '_detailError' if the detail
    fetch itself failed."""
    try:
        detail = await _fetch_full_detail(id_compra, proxy_url_fn)
    except RecordNotFound:
        return {"_detailError": "not_found"}
    except TRANSIENT_ERRORS as e:
        return {"_detailError": repr(e)}
    detail.pop("_input", None)
    detail.pop("_source", None)
    detail.pop("_scrapedAt", None)
    return detail


async def run_list(year: int | None, month: int | None, max_results: int, fetch_detail: bool, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        items = await fetch_rss(year, month, proxy_url=proxy_url)
    except TRANSIENT_ERRORS as e:
        window = f"year={year}:month={month}" if year and month else "latest"
        return [build_error_record(f"list:{window}", "blocked_or_transient", repr(e))]

    records: list[dict] = []
    for item in items[:max_results]:
        rec = build_list_record(item)  # raises UnexpectedShape -- not swallowed
        if fetch_detail:
            rec.update(await _enrich_with_detail(rec["idCompra"], proxy_url_fn))
        records.append(rec)

    return records


async def run_detail(id_compras: list[int], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(id_compras)

    async def _one(i: int, id_compra: int):
        async with sem:
            try:
                results[i] = await _fetch_full_detail(id_compra, proxy_url_fn)
            except RecordNotFound:
                results[i] = build_error_record(str(id_compra), "not_found", "no record exists for this idCompra")
            except TRANSIENT_ERRORS as e:
                results[i] = build_error_record(str(id_compra), "blocked_or_transient", repr(e))
            # UnexpectedShape intentionally not caught -- raises and stops the run.

    await asyncio.gather(*(_one(i, id_compra) for i, id_compra in enumerate(id_compras)))
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
            year = input_data.get("year")
            month = input_data.get("month")
            year = int(year) if year else None
            month = int(month) if month else None
            if bool(year) != bool(month):
                raise input_error(
                    f"year and month must be provided together (or both omitted for the latest 500 releases) -- "
                    f"ARCE's own RSS feed 404s on year-only, see CRAWLING_METHOD.md. Got year={year!r} month={month!r}"
                )
            if year is not None and not (MIN_YEAR <= year <= 2100):
                raise input_error(f"year must be >= {MIN_YEAR}, got {year}")
            if month is not None and not (1 <= month <= 12):
                raise input_error(f"month must be 1-12, got {month}")

            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, MAX_LIST_RESULTS))
            fetch_detail = bool(input_data.get("fetchDetail", False))

            Actor.log.info(f"mode=list year={year} month={month} maxResults={max_results} fetchDetail={fetch_detail}")
            records = await run_list(year, month, max_results, fetch_detail, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("idCompra"):
            raw_ids.append(input_data["idCompra"])
        raw_ids.extend(input_data.get("idCompras") or [])
        id_compras: list[int] = []
        seen = set()
        for raw in raw_ids:
            s = str(raw).strip()
            # Accept a bare id_compra ("1367008") or a full ocid
            # ("ocds-yfs5dr-1367008") for convenience -- either form appears
            # in this actor's own list-mode/detail-mode output.
            if "-" in s and not s.lstrip("-").isdigit():
                s = s.rsplit("-", 1)[-1]
            if not s.isdigit():
                continue
            id_compra = int(s)
            if id_compra not in seen:
                seen.add(id_compra)
                id_compras.append(id_compra)
        if not id_compras:
            raise input_error(
                "Provide 'idCompra' or a non-empty 'idCompras' array (ARCE purchase IDs, "
                "e.g. from a 'list' mode run's idCompra field, or an ocds-yfs5dr-<id> ocid)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(id_compras)} idCompra(s), maxConcurrency={max_concurrency}")
        records = await run_detail(id_compras, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
