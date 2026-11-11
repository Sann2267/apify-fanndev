import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import CAIPOClient
from src.extractor import SearchApiError, build_error, build_record
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(
    query: str,
    search_field: str,
    condition: str,
    category: str | None,
    max_results: int,
    proxy_config,
) -> list[dict]:
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = CAIPOClient(proxy_url)
    try:
        name = query if search_field == "name" else None
        number = query if search_field == "number" else None
        rows, total, truncated = await client.search(
            name=name,
            name_condition=condition,
            number=number,
            number_condition=condition,
            category=category,
        )
        if not rows:
            return [build_error(query, "not_found")]
        return [build_record(query, row, total, truncated) for row in rows[:max_results]]
    except SearchApiError as e:
        return [build_error(query, "search_api_error", str(e))]
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        category = input_data.get("category") or None
        if not queries and not category:
            raise input_error(
                "Provide 'query' or 'queries' (a company/business name or CAIPO registration "
                "number), and/or a 'category' filter."
            )
        if not queries:
            # category-only search: one pass with no name/number filter
            queries = [""]

        search_field = input_data.get("searchField") or "name"
        condition = input_data.get("condition") or "Contains"
        max_results = min(int(input_data.get("maxResultsPerQuery", 100)), 2000)
        max_concurrency = min(int(input_data.get("maxConcurrency", 3)), 10)

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(query: str):
            async with sem:
                return await search_one_query(query, search_field, condition, category, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), searchField={search_field!r}, "
            f"condition={condition!r}, category={category!r}, maxResultsPerQuery={max_results}"
        )
        results = await asyncio.gather(*(_bounded(q) for q in queries))

        for records in results:
            for record in records:
                await Actor.push_data(record)
