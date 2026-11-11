import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import OCRClient
from src.extractor import NoResultsFound, build_error, build_record, build_request_body, extract_records
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, search_by: str, max_results: int, proxy_config) -> dict:
    """Runs one stateless search call. Returns `{"records": [...]}` or
    `{"error": <record>}`. No session/cookie affinity needed -- every call
    is independent, so a fresh client per query is fine for concurrency."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = OCRClient(proxy_url)
    try:
        body = build_request_body(query, search_by)
        payload = await client.search_company(body)
        try:
            rows = extract_records(payload)
        except NoResultsFound:
            return {"error": build_error(query, "not_found")}
        total = len(rows)
        rows = rows[:max_results]
        if total > len(rows):
            log.info(f"{query!r} matched {total} companies -- keeping first {len(rows)} (maxResultsPerQuery)")
        return {"records": [build_record(query, row) for row in rows]}
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": build_error(query, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        queries = [q for q in queries if q and q.strip()]
        if not queries:
            raise input_error("Provide 'query' or 'queries' -- a company name (English or Nepali) or OCR registration number.")

        search_by = input_data.get("searchBy") or "auto"
        max_results = min(int(input_data.get("maxResultsPerQuery", 50)), 2000)
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, search_by, max_results, proxy_config)

        Actor.log.info(f"Searching {len(queries)} quer(y/ies), searchBy={search_by!r}, maxResultsPerQuery={max_results}")
        outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for outcome in outcomes:
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
            else:
                for record in outcome["records"]:
                    await Actor.push_data(record)
