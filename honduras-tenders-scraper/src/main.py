import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, HonduComprasClient
from src.constants import ETAPA_VALUES, MODALIDAD_VALUES, TIPO_ADQUISICION_VALUES
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record, parse_detail
from src.input_errors import input_error


def _enum_value(mapping: dict, key: str | None, field_name: str) -> str:
    if not key:
        return "0"
    value = mapping.get(key)
    if value is None:
        raise ValueError(f"{field_name} must be one of {sorted(mapping)}, got {key!r}")
    return value


async def run_list(input_data: dict, proxy_url_fn) -> list[dict]:
    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 1000))

    etapa = _enum_value(ETAPA_VALUES, input_data.get("etapa"), "etapa")
    modalidad = _enum_value(MODALIDAD_VALUES, input_data.get("modalidad"), "modalidad")
    tipo_adquisicion = _enum_value(TIPO_ADQUISICION_VALUES, input_data.get("tipoAdquisicion"), "tipoAdquisicion")

    proxy_url = await proxy_url_fn()
    client = HonduComprasClient(proxy_url)
    try:
        rows, filters_used = await client.search_list(
            entidad_query=input_data.get("entidad"),
            etapa=etapa,
            modalidad=modalidad,
            tipo_adquisicion=tipo_adquisicion,
            expediente=str(input_data.get("expediente") or ""),
            fecha_inicio=str(input_data.get("fechaInicio") or ""),
            fecha_fin=str(input_data.get("fechaFin") or ""),
            max_results=max_results,
        )
    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return [build_error_record(input_data, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if not rows:
        return [build_error_record(filters_used, "not_found", "search matched zero tenders")]

    records = [build_list_record(row, filters_used) for row in rows]

    if input_data.get("fetchDetail"):
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))
        sem = asyncio.Semaphore(max_concurrency)

        async def _enrich(record: dict):
            url = record.get("detailUrl")
            if not url:
                return
            async with sem:
                proxy_url = await proxy_url_fn()
                detail_client = HonduComprasClient(proxy_url)
                try:
                    html = await detail_client.fetch_detail(url)
                    detail = parse_detail(html, url)  # raises UnexpectedShape -- not swallowed
                    record.update({k: v for k, v in detail.items() if k not in ("url",)})
                except (RuntimeError, RequestException, ConnectionError) as e:
                    record["_detailError"] = repr(e)
                finally:
                    await detail_client.close()

        await asyncio.gather(*(_enrich(r) for r in records))

    return records


async def run_detail(urls: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(urls)

    async def _one(i: int, url: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            client = HonduComprasClient(proxy_url)
            try:
                html = await client.fetch_detail(url)
                detail = parse_detail(html, url)  # raises UnexpectedShape -- not swallowed
                results[i] = build_detail_record(url, detail)
            except (RuntimeError, RequestException, ConnectionError, FetchFailed) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from
                # the builtin one (parallel MRO, same name) -- both listed.
                results[i] = build_error_record(url, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, url) for i, url in enumerate(urls)))
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
                f"mode=list entidad={input_data.get('entidad')!r} etapa={input_data.get('etapa')!r} "
                f"maxResults={input_data.get('maxResults', 50)} fetchDetail={bool(input_data.get('fetchDetail'))}"
            )
            records = await run_list(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_urls = []
        if input_data.get("url"):
            raw_urls.append(input_data["url"])
        raw_urls.extend(input_data.get("urls") or [])
        urls = []
        seen = set()
        for raw in raw_urls:
            url = str(raw).strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        if not urls:
            raise input_error(
                "Provide 'url' or a non-empty 'urls' array -- a ProcesoHistorico.aspx detail link "
                "(e.g. the 'detailUrl' field from a 'list' mode run)."
            )

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 6))

        Actor.log.info(f"mode=detail {len(urls)} url(s), maxConcurrency={max_concurrency}")
        records = await run_detail(urls, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
