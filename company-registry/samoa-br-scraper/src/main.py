import asyncio
import logging
import math

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import SamoaBRClient
from src.constants import RESULTS_PAGE_SIZE
from src.extractor import NoResultsFound, build_detail_record, build_summary_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, max_results: int, proxy_config) -> dict:
    """Runs one guest search session end-to-end: search page 1, then
    additional pages (if `max_results` needs them, up to 10 pages / 100
    rows) via `selectPage`. Returns either `{"rows": [...]}` or
    `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = SamoaBRClient(proxy_url)
    try:
        session = await client.start_search()
        try:
            rows = await client.search(session, query)
        except NoResultsFound:
            return {"error": extract_error(query, "not_found")}
        pages_needed = min(math.ceil(max_results / RESULTS_PAGE_SIZE), 10)
        page = 2
        while len(rows) < max_results and page <= pages_needed:
            more = await client.next_page(session, page)
            if not more:
                break
            rows.extend(more)
            page += 1
        return {"rows": rows[:max_results]}
    except (RuntimeError, RequestException, ConnectionError) as e:
        return {"error": extract_error(query, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def fetch_detail_record(query: str, row: dict, proxy_config) -> dict:
    """Opens one search result's detail view + all tabs in a FRESH client
    (own session/cookies): re-runs the same search to land back on the
    matching row's click-through node id, since that id is scoped to the
    session that produced it and can't be reused across a different one."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = SamoaBRClient(proxy_url)
    try:
        search_session = await client.start_search()
        try:
            rows = await client.search(search_session, query)
        except NoResultsFound:
            return extract_error(query, "detail_fetch_failed", "result disappeared on re-search")
        match = next((r for r in rows if r["registrationNumber"] == row["registrationNumber"]), None)
        if match is None:
            return extract_error(query, "detail_fetch_failed", "result not found on re-search for detail fetch")
        detail = await client.fetch_full_detail(search_session, match)
        return build_detail_record(query, row, detail)
    except (RuntimeError, RequestException, ConnectionError) as e:
        return extract_error(query, "detail_fetch_failed", repr(e))
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
                "Provide 'query' or 'queries' -- a company name (or partial name) or Samoa registration number."
            )

        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 100)
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return query, await search_one_query(query, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), maxResultsPerQuery={max_results}, fetchDetails={fetch_details}"
        )
        search_outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        all_rows: list[tuple[str, dict]] = []
        for query, outcome in search_outcomes:
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
            else:
                all_rows.extend((query, row) for row in outcome["rows"])

        if not fetch_details:
            for query, row in all_rows:
                await Actor.push_data(build_summary_record(query, row))
            return

        Actor.log.info(f"Fetching full profiles for {len(all_rows)} matched compan(y/ies)")

        async def _bounded_detail(query: str, row: dict):
            async with sem:
                record = await fetch_detail_record(query, row, proxy_config)
                await Actor.push_data(record)

        await asyncio.gather(*(_bounded_detail(q, r) for q, r in all_rows))
