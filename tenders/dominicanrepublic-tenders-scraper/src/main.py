import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_procesos, fetch_proceso_detail
from src.constants import MAX_LIST_PAGES_SAFETY_CAP, MAX_PAGE_LIMIT, LIST_PAGE_DELAY
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error


async def _enrich_with_detail(codigo_proceso: str, proxy_url_fn) -> dict:
    """Best-effort enrichment for list mode -- never raises. Adds the
    contratos/ofertas/articulos detail onto a list row, or '_detailError' if
    the detail fetch itself failed."""
    proxy_url = await proxy_url_fn()
    try:
        data = await fetch_proceso_detail(codigo_proceso, proxy_url=proxy_url)
    except RecordNotFound:
        return {"_detailError": "not_found"}
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return {"_detailError": repr(e)}
    detail = build_detail_record(codigo_proceso, data)  # raises UnexpectedShape -- not swallowed
    detail.pop("_input", None)
    detail.pop("_source", None)
    detail.pop("_scrapedAt", None)
    return detail


def _filters_desc(**filters) -> str:
    parts = [f"{k}={v}" for k, v in filters.items() if v not in (None, "", False)]
    return ":".join(parts) if parts else "all"


async def run_list(
    estado: str,
    modalidad: str,
    unidad_compra,
    mipyme,
    mipyme_mujer,
    start_date: str,
    end_date: str,
    proceso_code: str,
    max_results: int,
    fetch_detail: bool,
    proxy_url_fn,
) -> list[dict]:
    records: list[dict] = []
    page = 1
    pages_fetched = 0
    filters_desc = _filters_desc(
        estado=estado,
        modalidad=modalidad,
        unidad_compra=unidad_compra,
        mipyme=mipyme,
        mipyme_mujer=mipyme_mujer,
        startdate=start_date,
        enddate=end_date,
        proceso=proceso_code,
    )
    limit = max(1, min(max_results, MAX_PAGE_LIMIT))

    while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
        proxy_url = await proxy_url_fn()
        try:
            result = await fetch_procesos(
                page=page,
                limit=limit,
                proceso=proceso_code,
                unidad_compra=unidad_compra,
                modalidad=modalidad,
                estado=estado,
                mipyme=mipyme,
                mipyme_mujer=mipyme_mujer,
                startdate=start_date,
                enddate=end_date,
                proxy_url=proxy_url,
            )
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:{filters_desc}:page={page}", "blocked_or_transient", repr(e)))
            break

        pages_fetched += 1
        rows = (result.get("payload") or {}).get("content") or []
        if not rows:
            Actor.log.info(f"list: no more rows at page={page} -- reached the end of the result set.")
            break

        for row in rows:
            rec = build_list_record(row, filters_desc)  # raises UnexpectedShape -- not swallowed
            if fetch_detail and rec.get("codigo_proceso"):
                rec.update(await _enrich_with_detail(rec["codigo_proceso"], proxy_url_fn))
            records.append(rec)
            if len(records) >= max_results:
                break

        total_pages = result.get("pages")
        if isinstance(total_pages, int) and page >= total_pages:
            Actor.log.info(f"list: reached upstream's last page ({total_pages}).")
            break

        page += 1
        if len(records) < max_results:
            await asyncio.sleep(LIST_PAGE_DELAY)

    if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
        Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")

    return records


async def run_detail(codigos: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(codigos)

    async def _one(i: int, codigo: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                data = await fetch_proceso_detail(codigo, proxy_url=proxy_url)
            except RecordNotFound:
                results[i] = build_error_record(codigo, "not_found", "no proceso exists for this code")
                return
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from
                # the builtin one (parallel MRO, same name) -- both listed,
                # per the portfolio-wide Babak 22b fix.
                results[i] = build_error_record(codigo, "blocked_or_transient", repr(e))
                return
            results[i] = build_detail_record(codigo, data)  # raises UnexpectedShape -- not swallowed

    await asyncio.gather(*(_one(i, codigo) for i, codigo in enumerate(codigos)))
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
            estado = str(input_data.get("estado") or "").strip()
            modalidad = str(input_data.get("modalidad") or "").strip()
            unidad_compra = input_data.get("unidadCompra") or None
            mipyme = input_data.get("mipyme")
            mipyme_mujer = input_data.get("mipymeMujer")
            start_date = str(input_data.get("startDate") or "").strip()
            end_date = str(input_data.get("endDate") or "").strip()
            proceso_code = str(input_data.get("procesoCode") or "").strip()
            max_results = int(input_data.get("maxResults", 25))
            max_results = max(1, min(max_results, 2000))
            fetch_detail = bool(input_data.get("fetchDetail", False))

            Actor.log.info(
                f"mode=list estado={estado!r} modalidad={modalidad!r} unidadCompra={unidad_compra!r} "
                f"startDate={start_date!r} endDate={end_date!r} procesoCode={proceso_code!r} "
                f"maxResults={max_results} fetchDetail={fetch_detail}"
            )
            records = await run_list(
                estado,
                modalidad,
                unidad_compra,
                mipyme,
                mipyme_mujer,
                start_date,
                end_date,
                proceso_code,
                max_results,
                fetch_detail,
                proxy_url_fn,
            )
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_codes = []
        if input_data.get("procesoCode"):
            raw_codes.append(input_data["procesoCode"])
        raw_codes.extend(input_data.get("procesoCodes") or [])
        codes = []
        seen = set()
        for raw in raw_codes:
            code = str(raw).strip()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        if not codes:
            raise input_error(
                "Provide 'procesoCode' or a non-empty 'procesoCodes' array (DGCP proceso codes, "
                "e.g. from a 'list' mode run's codigo_proceso field)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(codes)} proceso code(s), maxConcurrency={max_concurrency}")
        records = await run_detail(codes, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
