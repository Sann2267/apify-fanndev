import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import CIPOClient
from src.extractor import InvalidQuery, NoResultsFound, UpstreamError, build_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)

RETRYABLE = (RuntimeError, ConnectionError, RequestException)


async def search_one_query(query: str, search_type: str, max_results: int, fetch_details: bool, proxy_config) -> list[dict]:
    """Runs one guest search end-to-end (stateless -- no session/transaction
    needed, unlike the Verne-based registries in this project). Returns a
    list of dataset-ready records (never raises)."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = CIPOClient(proxy_url)
    try:
        try:
            rows = await client.search(query, search_type)
        except InvalidQuery as e:
            return [extract_error(query, search_type, "invalid_query", str(e))]
        except NoResultsFound:
            return [extract_error(query, search_type, "not_found")]
        except UpstreamError as e:
            return [extract_error(query, search_type, "upstream_error", str(e))]

        rows = rows[:max_results]
        if not fetch_details:
            return [build_record(query, search_type, row) for row in rows]

        async def _detail_for(row: dict) -> dict:
            entity_id = row.get("EntityID")
            if not entity_id:
                return build_record(query, search_type, row)
            try:
                detail = await client.entity_info(entity_id)
            except RETRYABLE as e:
                log.warning(f"entity_info failed for {entity_id!r} ({query!r}): {e!r}")
                return build_record(query, search_type, row)
            return build_record(query, search_type, row, detail)

        return await asyncio.gather(*(_detail_for(row) for row in rows))
    except RETRYABLE as e:
        return [extract_error(query, search_type, "blocked_or_transient", repr(e))]
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
                "Provide 'query' or 'queries' -- an entity name/registration number, "
                "director surname, or shareholder name, depending on 'searchType'."
            )

        search_type = input_data.get("searchType") or "entities"
        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 200)
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(query: str):
            async with sem:
                return await search_one_query(query, search_type, max_results, fetch_details, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), searchType={search_type!r}, "
            f"maxResultsPerQuery={max_results}, fetchDetails={fetch_details}"
        )
        results = await asyncio.gather(*(_bounded(q) for q in queries))

        for records in results:
            for record in records:
                await Actor.push_data(record)
