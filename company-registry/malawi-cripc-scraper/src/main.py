import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import MBRSClient
from src.constants import MAX_PAGES_PER_QUERY
from src.extractor import (
    SOURCE,
    SOURCE_DETAIL,
    build_record,
    extract_error,
    parse_entity_page,
    parse_individual_page,
    parse_owner_detail,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def _enrich_owner_details(client: MBRSClient, items: list[dict]) -> bool:
    """Fetches the owner-detail page for each individual result that has one
    and merges in `ownerIdType`/`businesses`. Returns True if any enrichment
    call failed (non-fatal -- the base search-result fields are kept either
    way)."""
    any_failed = False
    for item in items:
        owner_id = item.get("ownerId")
        if not owner_id:
            continue
        try:
            html = await client.fetch_owner_detail(owner_id)
            detail = parse_owner_detail(html)
            item["ownerIdType"] = detail["ownerIdType"]
            item["businesses"] = detail["businesses"]
            if detail["ownerName"]:
                item["name"] = detail["ownerName"]
        except (RuntimeError, RequestException, ConnectionError) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from
            # the builtin one (parallel MRO, same name) -- both listed.
            item["_ownerDetailError"] = repr(e)[:300]
            any_failed = True
    return any_failed


async def search_one_query(
    query: str,
    search_type: str,
    max_results: int,
    include_owner_details: bool,
    proxy_config,
) -> dict:
    """Runs one name-search query end-to-end (with internal pagination and,
    for individual searches, optional owner-detail enrichment). Returns
    `{"items": [...], "truncated": bool}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = MBRSClient(proxy_url)
    parse_page = parse_entity_page if search_type == "entity" else parse_individual_page
    try:
        items: list[dict] = []
        page = 1
        truncated = False
        while len(items) < max_results:
            if page > MAX_PAGES_PER_QUERY:
                truncated = True
                break
            html = await client.fetch_search_page(search_type, query, page)
            page_items = parse_page(html)
            if not page_items:
                break
            items.extend(page_items)
            page += 1
        items = items[:max_results]

        if not items:
            return {"error": extract_error(query, search_type, "not_found")}

        detail_failed = False
        if search_type == "individual" and include_owner_details:
            detail_failed = await _enrich_owner_details(client, items)

        return {"items": items, "truncated": truncated, "detail_failed": detail_failed}
    except (RuntimeError, RequestException, ConnectionError) as e:
        return {"error": extract_error(query, search_type, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error("Provide 'query' or 'queries' -- a company/business name or a person's name to search for.")

        search_type = input_data.get("searchType", "entity")
        if search_type not in ("entity", "individual"):
            raise input_error(f"searchType must be 'entity' or 'individual', got {search_type!r}")

        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 500)
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        include_owner_details = bool(input_data.get("includeOwnerDetails", True))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, search_type, max_results, include_owner_details, proxy_config)

        Actor.log.info(f"Searching {len(queries)} quer(y/ies), type={search_type}, maxResultsPerQuery={max_results}")
        outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for query, outcome in zip(queries, outcomes):
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            source = SOURCE_DETAIL if (search_type == "individual" and include_owner_details) else SOURCE
            warning = None
            if outcome.get("truncated"):
                warning = "pagination_truncated_by_page_cap"
            elif outcome.get("detail_failed"):
                warning = "owner_detail_fetch_partially_failed"
            for entity in outcome["items"]:
                await Actor.push_data(build_record(query, search_type, entity, source=source, warning=warning))
