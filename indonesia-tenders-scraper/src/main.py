import asyncio
from datetime import datetime, timezone

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, SpseSession
from src.constants import LIST_PAGE_DELAY, LIST_PAGE_SIZE, MAX_LIST_PAGES_SAFETY_CAP
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error


async def run_list(
    tahun: int | None,
    kategori_id: str,
    instansi_id: str,
    rekanan: str,
    max_results: int,
    fetch_detail: bool,
    proxy_url_fn,
) -> list[dict]:
    records: list[dict] = []
    start = 0
    pages_fetched = 0
    proxy_url = await proxy_url_fn()
    spse = SpseSession(proxy_url=proxy_url)
    input_tag = f"list:tahun={tahun}" + (f":kategoriId={kategori_id}" if kategori_id else "") + (
        f":instansiId={instansi_id}" if instansi_id else ""
    ) + (f":rekanan={rekanan}" if rekanan else "")

    try:
        await spse.warm_up(tahun=tahun, kategori_id=kategori_id, instansi_id=instansi_id, rekanan=rekanan)
        while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
            length = min(LIST_PAGE_SIZE, max_results - len(records))
            try:
                page = await spse.fetch_list_page(start, length)
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                records.append(build_error_record(f"{input_tag}:start={start}", "blocked_or_transient", repr(e)))
                break

            pages_fetched += 1
            rows = page.get("data") if isinstance(page, dict) else None
            if not rows:
                Actor.log.info(f"list: no more rows at start={start} -- reached the end of the listing.")
                break

            for row in rows:
                rec = build_list_record(row, input_tag)  # raises UnexpectedShape -- not swallowed
                if fetch_detail and rec.get("kode"):
                    rec.update(await _enrich_with_detail(spse, rec["kode"]))
                records.append(rec)
                if len(records) >= max_results:
                    break

            start += length
            if len(records) < max_results:
                await asyncio.sleep(LIST_PAGE_DELAY)

        if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
            Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")
    finally:
        await spse.close()

    return records


async def _enrich_with_detail(spse: SpseSession, kode: str) -> dict:
    """Best-effort enrichment for list mode -- never raises. Adds the full
    detail-page fields onto a list row, or '_detailError' if that row's own
    detail fetch failed."""
    try:
        html_text = await spse.fetch_detail(kode)
    except RecordNotFound:
        return {"_detailError": "not_found"}
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        return {"_detailError": repr(e)}
    detail = build_detail_record(kode, html_text)  # raises UnexpectedShape -- not swallowed
    detail.pop("_input", None)
    detail.pop("_source", None)
    detail.pop("_scrapedAt", None)
    detail.pop("kode", None)
    return detail


async def run_detail(kodes: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(kodes)

    async def _one(i: int, kode: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            spse = SpseSession(proxy_url=proxy_url)
            try:
                try:
                    html_text = await spse.fetch_detail(kode)
                except RecordNotFound:
                    results[i] = build_error_record(kode, "not_found", "no tender exists for this code")
                    return
                except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                    # NOTE: curl_cffi's own ConnectionError does not inherit from
                    # the builtin one (parallel MRO, same name) -- both listed,
                    # per the portfolio-wide Babak 22b fix.
                    results[i] = build_error_record(kode, "blocked_or_transient", repr(e))
                    return
                results[i] = build_detail_record(kode, html_text)  # raises UnexpectedShape -- not swallowed
            finally:
                await spse.close()

    await asyncio.gather(*(_one(i, kode) for i, kode in enumerate(kodes)))
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
            tahun = input_data.get("tahunAnggaran")
            tahun = int(tahun) if tahun else datetime.now(timezone.utc).year
            kategori_id = str(input_data.get("kategoriId") or "").strip()
            instansi_id = str(input_data.get("instansiId") or "").strip()
            rekanan = str(input_data.get("rekanan") or "").strip()
            max_results = int(input_data.get("maxResults", 25))
            max_results = max(1, min(max_results, 5000))
            fetch_detail = bool(input_data.get("fetchDetail", False))

            Actor.log.info(
                f"mode=list tahunAnggaran={tahun} kategoriId={kategori_id!r} instansiId={instansi_id!r} "
                f"rekanan={rekanan!r} maxResults={max_results} fetchDetail={fetch_detail}"
            )
            records = await run_list(
                tahun, kategori_id, instansi_id, rekanan, max_results, fetch_detail, proxy_url_fn
            )
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("kode"):
            raw_ids.append(input_data["kode"])
        raw_ids.extend(input_data.get("kodes") or [])
        kodes = []
        seen = set()
        for raw in raw_ids:
            kode = str(raw).strip()
            if kode and kode not in seen:
                seen.add(kode)
                kodes.append(kode)
        if not kodes:
            raise input_error(
                "Provide 'kode' or a non-empty 'kodes' array (SPSE tender codes, "
                "e.g. from a 'list' mode run's kode field)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(kodes)} kode(s), maxConcurrency={max_concurrency}")
        records = await run_detail(kodes, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
