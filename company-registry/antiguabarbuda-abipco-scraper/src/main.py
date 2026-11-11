import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ABIPCOClient
from src.constants import SERVER_RESULT_CAP
from src.extractor import build_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, max_results: int, proxy_config) -> list[dict]:
    """Runs one search and returns a list of dataset-ready records (either
    real match rows, or a single `_error` record)."""
    stripped = query.strip() if isinstance(query, str) else ""
    if not stripped:
        # A blank/whitespace-only query makes the upstream API return HTTP
        # 500 -- rejected here before making the request. See constants.py.
        return [extract_error(query, "invalid_query", "Query is blank or whitespace-only.")]

    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ABIPCOClient(proxy_url)
    try:
        rows = await client.search(stripped)
        if not rows:
            return [extract_error(query, "not_found")]
        return [build_record(query, row) for row in rows[:max_results]]
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        log.warning(f"search failed for {query!r}: {e!r}")
        return [extract_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error(
                "Provide 'query' or 'queries' -- an entity name (or partial name) or ABIPCO registration number."
            )

        max_results = min(int(input_data.get("maxResultsPerQuery", SERVER_RESULT_CAP)), SERVER_RESULT_CAP)
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, max_results, proxy_config)

        Actor.log.info(f"Searching {len(queries)} quer(y/ies), maxResultsPerQuery={max_results}")
        results = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for records in results:
            for record in records:
                await Actor.push_data(record)
