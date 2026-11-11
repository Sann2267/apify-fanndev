import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, SigmapClient
from src.constants import LIST_CONFIGS, VALID_LIST_TYPES
from src.extractor import UnexpectedShape, build_error_record, build_list_record, parse_publication_grid
from src.input_errors import input_error


async def _run_one_list_type(client: SigmapClient, list_type: str, max_results: int) -> list[dict]:
    cfg = LIST_CONFIGS[list_type]
    try:
        html_text = await client.fetch_category_page(cfg["jsf_id"])
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed, per the
        # portfolio-wide Babak 22b fix.
        return [build_error_record(f"list:{list_type}", "blocked_or_transient", repr(e))]

    rows = parse_publication_grid(html_text)  # raises UnexpectedShape -- must NOT be swallowed
    records = []
    for row in rows:
        records.append(build_list_record(list_type, cfg["group"], row))
        if len(records) >= max_results:
            break
    return records


async def run_list(list_type: str, max_results: int, proxy_url: str | None) -> list[dict]:
    client = SigmapClient(proxy_url=proxy_url)
    try:
        if list_type == "all":
            records: list[dict] = []
            for lt in LIST_CONFIGS:
                remaining = max_results - len(records)
                if remaining <= 0:
                    break
                records.extend(await _run_one_list_type(client, lt, remaining))
            return records
        return await _run_one_list_type(client, list_type, max_results)
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        list_type = input_data.get("listType", "all")
        if list_type not in VALID_LIST_TYPES:
            raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")
        max_results = int(input_data.get("maxResults", 200))
        max_results = max(1, min(max_results, 2000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"listType={list_type} maxResults={max_results}")
        records = await run_list(list_type, max_results, proxy_url)
        Actor.log.info(f"Pushing {len(records)} record(s).")
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
