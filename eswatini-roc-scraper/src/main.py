import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import EswatiniROCClient
from src.constants import MIN_QUERY_LENGTH
from src.extractor import NoResultsFound, build_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, max_results: int, proxy_config) -> dict:
    """Runs one search end-to-end and returns either
    `{"rows": [{"companyName", "companyStatus", "dateRegistered"}, ...]}`
    or `{"error": <record>}`."""
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return {
            "error": extract_error(
                query, "query_too_short", f"minimum {MIN_QUERY_LENGTH} characters required"
            )
        }

    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = EswatiniROCClient(proxy_url)
    try:
        try:
            rows = await client.search(query)
        except NoResultsFound:
            return {"error": extract_error(query, "not_found")}
        return {"rows": rows[:max_results]}
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
            raise input_error("Provide 'query' or 'queries' -- a company/business name (at least 3 characters).")

        max_results = min(int(input_data.get("maxResultsPerQuery", 50)), 1000)
        max_concurrency = int(input_data.get("maxConcurrency", 3))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, max_results, proxy_config)

        Actor.log.info(f"Searching {len(queries)} quer(y/ies), maxResultsPerQuery={max_results}")
        outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for query, outcome in zip(queries, outcomes):
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            for row in outcome["rows"]:
                await Actor.push_data(build_record(query, row))
