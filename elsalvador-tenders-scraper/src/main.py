import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ComprasalClient, FetchFailed
from src.constants import AWARDED_PAGE_SIZE, MAX_AWARDED_PAGES_SAFETY_CAP
from src.extractor import (
    UnexpectedShape,
    build_awarded_record,
    build_detail_record,
    build_error_record,
    build_open_record,
    parse_awarded_response,
    parse_detail_response,
    parse_institutions_response,
    parse_open_response,
    resolve_institution_id,
)
from src.input_errors import input_error

# NOTE (portfolio-wide Babak 22b fix): curl_cffi's own ConnectionError does
# not inherit from the builtin one (parallel MRO, same name) -- both must be
# listed in every top-level except tuple in this run-loop, or a real
# transient network failure would silently escape and crash the run instead
# of being turned into an `_error` record.
_TRANSIENT_EXC = (RuntimeError, RequestException, ConnectionError, FetchFailed)


async def _resolve_institucion_id(client: ComprasalClient, entidad_query: str | None) -> int | None:
    if not entidad_query:
        return None
    try:
        payload = await client.fetch_institutions()
        institutions = parse_institutions_response(payload)
        return resolve_institution_id(institutions, entidad_query)
    except _TRANSIENT_EXC + (UnexpectedShape,) as e:
        Actor.log.warning(f"institution lookup failed, proceeding unfiltered: {e!r}")
        return None


async def _enrich_with_detail(records: list[dict], id_fn, proxy_url_fn, max_concurrency: int):
    sem = asyncio.Semaphore(max_concurrency)

    async def _one(record: dict):
        process_id = id_fn(record)
        if process_id is None:
            return
        async with sem:
            proxy_url = await proxy_url_fn()
            client = ComprasalClient(proxy_url)
            try:
                payload = await client.fetch_detail(process_id)
                detail = parse_detail_response(payload)  # raises UnexpectedShape -- not swallowed
                record["detail"] = detail
            except _TRANSIENT_EXC as e:
                record["_detailError"] = repr(e)
            finally:
                await client.close()

    await asyncio.gather(*(_one(r) for r in records))


async def run_open(input_data: dict, proxy_url_fn) -> list[dict]:
    entidad = input_data.get("entidad")
    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 1000))

    proxy_url = await proxy_url_fn()
    client = ComprasalClient(proxy_url)
    try:
        institucion_id = await _resolve_institucion_id(client, entidad)
        filters_used = {"entidad": entidad or None, "institucionId": institucion_id}

        payload = await client.fetch_open(institucion_id=institucion_id)
        rows = parse_open_response(payload)
    except _TRANSIENT_EXC + (UnexpectedShape,) as e:
        # UnexpectedShape is caught HERE (top-level list fetch) so a shape
        # change surfaces as an honest `_error` record rather than crashing
        # the whole run -- but is deliberately NOT caught inside
        # `_enrich_with_detail`'s per-record loop below, matching the
        # portfolio-wide convention (see honduras-tenders-scraper/src/main.py).
        return [build_error_record(input_data, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if entidad and institucion_id is None:
        # Couldn't resolve the name to a known institution id -- fall back to
        # a client-side substring match against each row's own institution
        # name so the filter still does *something* useful.
        needle = entidad.strip().lower()
        rows = [r for r in rows if needle in (r.get("institucion") or "").lower()]

    if not rows:
        return [build_error_record(filters_used, "not_found", "no open processes matched")]

    records = [build_open_record(row, filters_used) for row in rows[:max_results]]

    if input_data.get("fetchDetail"):
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))
        await _enrich_with_detail(records, lambda r: r.get("id"), proxy_url_fn, max_concurrency)

    return records


async def run_awarded(input_data: dict, proxy_url_fn) -> list[dict]:
    entidad = input_data.get("entidad")
    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 5000))
    needle = (entidad or "").strip().lower()
    filters_used = {
        "entidad": entidad or None,
        "_note": "institucion/date filters are NOT server-side supported on this endpoint (verified during recon)"
        " -- 'entidad' is applied client-side after fetching each page."
        if entidad
        else None,
    }

    proxy_url = await proxy_url_fn()
    client = ComprasalClient(proxy_url)
    matched: list[dict] = []
    try:
        page = 1
        while len(matched) < max_results and page <= MAX_AWARDED_PAGES_SAFETY_CAP:
            payload = await client.fetch_awarded_page(page, AWARDED_PAGE_SIZE)
            rows = parse_awarded_response(payload)
            if not rows:
                break
            for row in rows:
                if needle:
                    inst_name = ((row.get("institucion") or {}).get("nombre")) or ""
                    if needle not in inst_name.lower():
                        continue
                matched.append(row)
                if len(matched) >= max_results:
                    break
            page += 1
    except _TRANSIENT_EXC + (UnexpectedShape,) as e:
        # Same top-level-only UnexpectedShape handling as run_open above.
        if matched:
            Actor.log.warning(f"awarded pagination stopped early after {len(matched)} matches: {e!r}")
        else:
            return [build_error_record(input_data, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if not matched:
        return [build_error_record(filters_used, "not_found", "no awarded processes matched")]

    records = [build_awarded_record(row, filters_used) for row in matched]

    if input_data.get("fetchDetail"):
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))
        await _enrich_with_detail(
            records, lambda r: (r.get("proceso_compra") or {}).get("id"), proxy_url_fn, max_concurrency
        )

    return records


async def run_detail(process_ids: list, max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(process_ids)

    async def _one(i: int, process_id):
        async with sem:
            proxy_url = await proxy_url_fn()
            client = ComprasalClient(proxy_url)
            try:
                payload = await client.fetch_detail(process_id)
                detail = parse_detail_response(payload)  # raises UnexpectedShape -- not swallowed
                results[i] = build_detail_record(process_id, detail)
            except _TRANSIENT_EXC as e:
                results[i] = build_error_record(process_id, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, pid) for i, pid in enumerate(process_ids)))
    return [r for r in results if r is not None]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "open")
        if mode not in ("open", "awarded", "detail"):
            raise input_error(f"mode must be 'open', 'awarded', or 'detail', got {mode!r}")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "open":
            Actor.log.info(
                f"mode=open entidad={input_data.get('entidad')!r} maxResults={input_data.get('maxResults', 50)} "
                f"fetchDetail={bool(input_data.get('fetchDetail'))}"
            )
            records = await run_open(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        if mode == "awarded":
            Actor.log.info(
                f"mode=awarded entidad={input_data.get('entidad')!r} maxResults={input_data.get('maxResults', 50)} "
                f"fetchDetail={bool(input_data.get('fetchDetail'))}"
            )
            records = await run_awarded(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("processId") is not None:
            raw_ids.append(input_data["processId"])
        raw_ids.extend(input_data.get("processIds") or [])
        process_ids = []
        seen = set()
        for raw in raw_ids:
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                continue
            if pid not in seen:
                seen.add(pid)
                process_ids.append(pid)
        if not process_ids:
            raise input_error(
                "Provide 'processId' or a non-empty 'processIds' array -- the numeric 'id' field "
                "from an 'open' mode record, or the 'proceso_compra.id' field from an 'awarded' mode record."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))

        Actor.log.info(f"mode=detail {len(process_ids)} process id(s), maxConcurrency={max_concurrency}")
        records = await run_detail(process_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
