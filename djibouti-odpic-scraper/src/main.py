import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ODPICClient
from src.constants import MAX_PAGES_PER_JOB, PER_PAGE
from src.extractor import UnexpectedShape, build_record, extract_error

log = logging.getLogger(__name__)

LATEST_LABEL = "(latest)"


async def run_one_job(
    query: str | None,
    date_from: str | None,
    date_to: str | None,
    order_by: str,
    order_direction: str,
    max_results: int,
    proxy_config,
) -> dict:
    """Runs one filter set (a search term, or a plain date-ordered browse
    when `query` is None) end-to-end, paginating until `max_results` is
    reached, upstream runs out of rows, or the safety page cap is hit.
    Returns `{"rows": [...], "truncated": bool}` or `{"error": <record>}`.
    """
    label = query if query else LATEST_LABEL
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ODPICClient(proxy_url)
    filters = {
        "search": query,
        "after": date_from,
        "before": date_to,
        "orderby": order_by,
        "order": order_direction,
    }
    try:
        rows: list[dict] = []
        page = 1
        truncated = False
        while len(rows) < max_results:
            if page > MAX_PAGES_PER_JOB:
                truncated = True
                break
            page_rows, total = await client.fetch_page(filters, page, per_page=PER_PAGE)
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(rows) >= total:
                break
            page += 1
        rows = rows[:max_results]
        if not rows:
            return {"error": extract_error(label, "not_found")}
        return {"rows": rows, "truncated": truncated}
    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": extract_error(label, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries: list[str | None] = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            queries = [None]  # no name given -> browse the latest filings

        date_from = (input_data.get("dateFrom") or "").strip() or None
        date_to = (input_data.get("dateTo") or "").strip() or None
        order_by = input_data.get("orderBy") or "date"
        order_direction = input_data.get("orderDirection") or "desc"
        max_results = min(int(input_data.get("maxResultsPerQuery", 100)), 5000)
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_job(query: str | None):
            async with sem:
                return await run_one_job(
                    query, date_from, date_to, order_by, order_direction, max_results, proxy_config
                )

        Actor.log.info(
            f"Running {len(queries)} job(s) (queries={[q or LATEST_LABEL for q in queries]}), "
            f"dateFrom={date_from}, dateTo={date_to}, orderBy={order_by}/{order_direction}, "
            f"maxResultsPerQuery={max_results}"
        )
        outcomes = await asyncio.gather(*(_bounded_job(q) for q in queries))

        for query, outcome in zip(queries, outcomes):
            label = query if query else LATEST_LABEL
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            if outcome.get("truncated"):
                log.warning(f"Job {label!r} hit the {MAX_PAGES_PER_JOB}-page safety cap before maxResultsPerQuery")
            for row in outcome["rows"]:
                await Actor.push_data(build_record(label, row))
