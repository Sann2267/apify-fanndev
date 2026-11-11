import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import SearchFailed, search
from src.constants import MIN_QUERY_LENGTH, UNSAFE_QUERY_CHARS
from src.extractor import (
    UnexpectedShape,
    build_available_record,
    build_error_record,
    build_match_record,
    parse_search_page,
)
from src.input_errors import input_error


async def process_query(query: str, max_results: int, proxy_url: str | None) -> list[dict]:
    unsafe = UNSAFE_QUERY_CHARS & set(query)
    if unsafe:
        return [
            build_error_record(
                query,
                "unsafe_query",
                f"Query contains {sorted(unsafe)!r} -- known to crash OARG's backend (upstream bug, "
                "not a transient failure). Query rejected client-side without sending a request.",
            )
        ]
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return [build_error_record(query, "invalid_query", f"Minimum length is {MIN_QUERY_LENGTH}")]

    try:
        html_text = await search(query, proxy_url=proxy_url)
    except (SearchFailed, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does NOT inherit from
        # Python's builtin ConnectionError -- both listed explicitly per
        # portfolio-wide convention.
        return [build_error_record(query, "blocked_or_transient", repr(e))]

    try:
        parsed = parse_search_page(html_text)
    except UnexpectedShape:
        # Fail loud on real schema drift -- must NOT be silently swallowed
        # into a generic error record, per project convention.
        raise

    if parsed["kind"] == "server_error":
        return [build_error_record(query, "upstream_backend_error", parsed["detail"])]
    if parsed["kind"] == "validation_error":
        return [build_error_record(query, "invalid_query", parsed["detail"])]
    if parsed["kind"] == "available":
        return [build_available_record(query)]

    matches = parsed["matches"]
    total_matches = len(matches)
    truncated = total_matches > max_results
    matches = matches[:max_results]
    return [build_match_record(query, m, total_matches, truncated) for m in matches]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = [q for q in (input_data.get("businessNames") or []) if isinstance(q, str) and q.strip()]
        if input_data.get("businessName"):
            queries.insert(0, input_data["businessName"])
        queries = [q.strip() for q in queries]
        if not queries:
            raise input_error("Provide 'businessName' or a non-empty 'businessNames' array.")

        max_results = int(input_data.get("maxResultsPerQuery", 200))
        max_results = max(1, min(max_results, 2000))

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(q: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                records = await process_query(q, max_results, proxy_url)
                await Actor.push_data(records)

        Actor.log.info(
            f"{len(queries)} quer{'y' if len(queries) == 1 else 'ies'}, "
            f"maxResultsPerQuery={max_results}, maxConcurrency={max_concurrency}"
        )
        await asyncio.gather(*(_bounded(q) for q in queries))
