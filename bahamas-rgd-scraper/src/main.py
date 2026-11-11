import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BahamasRGDClient, TooBroadError
from src.extractor import build_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, include_history: bool, proxy_config) -> dict:
    """Runs one company-name search end-to-end.
    Returns `{"items": [...]}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = BahamasRGDClient(proxy_url)
    try:
        items = await client.search(query, include_history)
        if not items:
            return {"error": extract_error(query, "not_found")}
        return {"items": items}
    except TooBroadError as e:
        return {"error": extract_error(query, "result_set_too_broad", repr(e))}
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": extract_error(query, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error("Provide 'query' or 'queries' -- a Bahamas company/business name to search for.")

        include_history = bool(input_data.get("includeHistory", False))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, include_history, proxy_config)

        Actor.log.info(f"Searching {len(queries)} quer(y/ies), includeHistory={include_history}")
        outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for query, outcome in zip(queries, outcomes):
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            for item in outcome["items"]:
                await Actor.push_data(build_record(query, item, include_history))
