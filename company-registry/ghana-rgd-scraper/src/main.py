import asyncio

from apify import Actor

from src.client import SearchFailed, search
from src.constants import VALID_SEARCH_TYPES
from src.extractor import (
    UnexpectedShape,
    build_empty_record,
    build_error_record,
    build_match_record,
    parse_search_fragment,
)
from src.input_errors import input_error


async def process_query(query: str, search_type: str, max_results: int, proxy_url: str | None) -> list[dict]:
    try:
        html_text = await search(query, search_type, proxy_url=proxy_url)
    except SearchFailed as e:
        return [build_error_record(query, search_type, "blocked_or_transient", repr(e))]

    try:
        parsed = parse_search_fragment(html_text)
    except UnexpectedShape as e:
        # Fail loud on real schema drift -- this must NOT be silently
        # swallowed into a generic error record, per project convention.
        raise

    if parsed["kind"] == "validation_error":
        return [build_error_record(query, search_type, "invalid_query", parsed["detail"])]

    if parsed["kind"] == "empty" or not parsed["matches"]:
        return [build_empty_record(query, search_type)]

    matches = parsed["matches"]
    total_available = parsed["totalAvailable"]
    truncated = len(matches) > max_results
    matches = matches[:max_results]
    return [build_match_record(query, search_type, m, total_available, truncated) for m in matches]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = [q for q in (input_data.get("businessNames") or []) if isinstance(q, str) and q.strip()]
        if input_data.get("businessName"):
            queries.insert(0, input_data["businessName"])
        queries = [q.strip() for q in queries]
        if not queries:
            raise input_error("Provide 'businessName' or a non-empty 'businessNames' array.")

        search_type = input_data.get("searchType", "cn")
        if search_type not in VALID_SEARCH_TYPES:
            raise input_error(f"searchType must be one of {sorted(VALID_SEARCH_TYPES)}, got {search_type!r}")

        max_results = int(input_data.get("maxResultsPerQuery", 200))
        max_results = max(1, min(max_results, 2000))

        max_concurrency = int(input_data.get("maxConcurrency", 2))
        max_concurrency = max(1, min(max_concurrency, 5))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(q: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                records = await process_query(q, search_type, max_results, proxy_url)
                await Actor.push_data(records)

        Actor.log.info(
            f"{len(queries)} quer{'y' if len(queries) == 1 else 'ies'}, "
            f"searchType={search_type}, maxResultsPerQuery={max_results}, maxConcurrency={max_concurrency}"
        )
        await asyncio.gather(*(_bounded(q) for q in queries))
