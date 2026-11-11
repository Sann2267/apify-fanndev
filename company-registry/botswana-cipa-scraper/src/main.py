import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import CIPAClient
from src.extractor import NoResultsFound, build_detail_record, build_summary_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, entity_type: str, max_results: int, proxy_config) -> dict:
    """Runs one guest search session end-to-end: search -> click each match
    to resolve its `entityView` permalink. Returns either
    `{"matches": [{"query", "row", "entityUrl"}, ...]}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = CIPAClient(proxy_url)
    try:
        session = await client.start_search()
        try:
            rows = await client.search(session, query, entity_type)
        except NoResultsFound:
            return {"error": extract_error(query, "not_found")}
        rows = rows[:max_results]
        matches = []
        for row in rows:
            try:
                entity_url = await client.open_entity(session, row["nodeId"])
            except (RuntimeError, RequestException, ConnectionError) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from
                # the builtin one (parallel MRO, same name) -- both listed.
                log.warning(f"open_entity failed for {row.get('label')!r} ({query!r}): {e!r}")
                matches.append({"query": query, "row": row, "entityUrl": None, "openError": repr(e)})
                continue
            matches.append({"query": query, "row": row, "entityUrl": entity_url})
        return {"matches": matches}
    except (RuntimeError, RequestException, ConnectionError) as e:
        return {"error": extract_error(query, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def fetch_detail_record(query: str, entity_url: str, proxy_config) -> dict:
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = CIPAClient(proxy_url)
    try:
        detail = await client.fetch_entity_detail(entity_url)
        return build_detail_record(query, entity_url, detail)
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
            raise input_error("Provide 'query' or 'queries' -- a company/business name or CIPA registration number.")

        entity_type = input_data.get("entityType") or "any"
        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 200)
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, entity_type, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), entityType={entity_type!r}, "
            f"maxResultsPerQuery={max_results}, fetchDetails={fetch_details}"
        )
        search_outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        all_matches = []
        for outcome in search_outcomes:
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
            else:
                all_matches.extend(outcome["matches"])

        if not fetch_details:
            for m in all_matches:
                if m["entityUrl"] is None:
                    await Actor.push_data(extract_error(m["query"], "click_failed", m.get("openError")))
                else:
                    await Actor.push_data(build_summary_record(m["query"], m["row"]))
            return

        matched_with_url = [m for m in all_matches if m["entityUrl"] is not None]
        for m in all_matches:
            if m["entityUrl"] is None:
                await Actor.push_data(extract_error(m["query"], "click_failed", m.get("openError")))

        Actor.log.info(f"Fetching full profiles for {len(matched_with_url)} matched entit(y/ies)")

        async def _bounded_detail(m: dict):
            async with sem:
                record = await fetch_detail_record(m["query"], m["entityUrl"], proxy_config)
                await Actor.push_data(record)

        await asyncio.gather(*(_bounded_detail(m) for m in matched_with_url))
