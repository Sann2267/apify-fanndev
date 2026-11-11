import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, SiscaeClient
from src.constants import ESTADO_VALUES, RESULTS_PER_PAGE_VALUES
from src.extractor import UnexpectedShape, build_error_record, build_list_record


def _resolve_estados(raw_estados) -> list[str]:
    if not raw_estados:
        return ["VIGENTE"]
    out = []
    for key in raw_estados:
        value = ESTADO_VALUES.get(str(key).strip().lower())
        if value is None:
            raise ValueError(f"estados values must be one of {sorted(ESTADO_VALUES)}, got {key!r}")
        if value not in out:
            out.append(value)
    return out


def _resolve_results_per_page(max_results: int) -> str:
    for cap, label in RESULTS_PER_PAGE_VALUES.items():
        if max_results <= cap:
            return label
    return RESULTS_PER_PAGE_VALUES[max(RESULTS_PER_PAGE_VALUES)]


async def run_search(input_data: dict, proxy_url_fn) -> list[dict]:
    max_results = int(input_data.get("maxResults", 50))
    max_results = max(1, min(max_results, 100))  # upstream page-size options cap at 100 -- see CRAWLING_METHOD.md

    estados = _resolve_estados(input_data.get("estados"))
    resultados_items = _resolve_results_per_page(max_results)

    proxy_url = await proxy_url_fn()
    client = SiscaeClient(proxy_url)
    try:
        rows, filters_used = await client.search(
            keyword=str(input_data.get("keyword") or ""),
            numero=str(input_data.get("numero") or ""),
            estados=estados,
            institucion_query=str(input_data.get("institucion") or ""),
            departamento_query=str(input_data.get("departamento") or ""),
            resultados_items=resultados_items,
        )
    except (RuntimeError, RequestException, ConnectionError, FetchFailed, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return [build_error_record(input_data, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if not rows:
        return [build_error_record(filters_used, "not_found", "search matched zero procedures")]

    return [build_list_record(row, filters_used) for row in rows[:max_results]]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(
            f"estados={input_data.get('estados')!r} keyword={input_data.get('keyword')!r} "
            f"institucion={input_data.get('institucion')!r} maxResults={input_data.get('maxResults', 50)}"
        )
        records = await run_search(input_data, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
