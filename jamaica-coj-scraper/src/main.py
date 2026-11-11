import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import COJClient
from src.constants import DEFAULT_REQUEST_DELAY_SECS, MAX_RESULTS_CAP
from src.extractor import NoResultsFound, build_error, build_record
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, max_results: int, proxy_config) -> dict:
    """Runs one search flow end-to-end. Returns
    `{"rows": [...]}` or `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = COJClient(proxy_url)
    try:
        try:
            rows = await client.search(query)
        except NoResultsFound:
            return {"error": build_error(query, "not_found")}
        return {"rows": rows[:max_results]}
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same class name) -- both listed.
        log.warning(f"search failed for {query!r}: {e!r}")
        return {"error": build_error(query, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error("Provide 'query' or 'queries' -- a company/business name or COJ registration number.")

        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), MAX_RESULTS_CAP)
        max_concurrency = int(input_data.get("maxConcurrency", 2))
        request_delay_secs = float(input_data.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str, index: int):
            async with sem:
                # Stagger query starts as a good-faith nod to the site's own
                # `Crawl-delay: 120` (see constants.py) without making a
                # multi-query run impractically slow -- see input description
                # for `requestDelaySecs`.
                if index > 0:
                    await asyncio.sleep(request_delay_secs)
                return await search_one_query(query, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), maxResultsPerQuery={max_results}, "
            f"maxConcurrency={max_concurrency}, requestDelaySecs={request_delay_secs}"
        )
        outcomes = await asyncio.gather(*(_bounded_search(q, i) for i, q in enumerate(queries)))

        for query, outcome in zip(queries, outcomes):
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            rows = outcome["rows"]
            if not rows:
                await Actor.push_data(build_error(query, "not_found"))
                continue
            for row in rows:
                await Actor.push_data(build_record(query, row))
