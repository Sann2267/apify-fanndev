import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NPCClient
from src.constants import BASE_URL, MAX_PAGES_PER_JOB, PER_PAGE, REST_TYPES, TENDER_ADVERTISEMENT_PATH
from src.extractor import (
    UnexpectedShape,
    build_listing_record,
    build_tender_record,
    extract_error,
    flatten_rest_row,
    parse_detail_fields,
    parse_tender_cards,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

# Network/upstream errors that mean "this specific round-trip failed" --
# degrade to a per-item/per-job error record. UnexpectedShape (payload-shape
# drift) is NOT caught here -- it propagates and fails the run loudly (see
# .ai/conventions/error-handling.md, Category 3, and .ai/CLAUDE.md
# principle 6). NOTE: curl_cffi's own ConnectionError does not inherit from
# the builtin one (parallel MRO, same name) -- both listed, per the
# portfolio-wide fix from Babak 22b.
TRANSIENT_ERRORS = (RuntimeError, ConnectionError, RequestException)


async def run_tenders_job(client: NPCClient) -> dict:
    """Fetches the live `/tender-advertisement/` page and parses every open
    tender card. This is the entire dataset the site exposes for open
    tenders -- no pagination exists (see constants.py)."""
    url = f"{BASE_URL}{TENDER_ADVERTISEMENT_PATH}"
    try:
        page_html = await client.fetch_html(url)
    except TRANSIENT_ERRORS as e:
        return {"error": extract_error("tenders", "blocked_or_transient", repr(e))}
    cards = parse_tender_cards(page_html)  # UnexpectedShape propagates
    if not cards:
        return {"error": extract_error("tenders", "not_found", "no open tenders currently listed")}
    return {"rows": [build_tender_record(c, url) for c in cards]}


async def run_rest_job(
    client: NPCClient,
    record_type: str,
    max_results: int,
    fetch_details: bool,
    max_concurrency: int,
) -> dict:
    """Discovers every `record_type` row via WordPress REST pagination, then
    (if `fetch_details`) fetches each detail page's HTML to pull the
    JetEngine labeled fields not present in the REST response."""
    post_type = REST_TYPES[record_type]  # e.g. "disposals" -> "disposals-notice"
    try:
        rows: list[dict] = []
        page = 1
        truncated = False
        while len(rows) < max_results:
            if page > MAX_PAGES_PER_JOB:
                truncated = True
                break
            page_rows, total = await client.fetch_rest_page(post_type, page, per_page=PER_PAGE)
            if not page_rows:
                break
            rows.extend(flatten_rest_row(r, post_type) for r in page_rows)  # UnexpectedShape propagates
            if len(rows) >= total:
                break
            page += 1
        rows = rows[:max_results]
    except TRANSIENT_ERRORS as e:
        return {"error": extract_error(post_type, "blocked_or_transient", repr(e))}

    if not rows:
        return {"error": extract_error(post_type, "not_found")}
    if truncated:
        log.warning(f"{post_type}: hit the {MAX_PAGES_PER_JOB}-page safety cap before maxResultsPerType")

    if not fetch_details:
        return {"rows": [build_listing_record(r, None) for r in rows]}

    sem = asyncio.Semaphore(max_concurrency)
    records: list[dict] = [None] * len(rows)

    async def _fetch_one(i: int, row: dict):
        async with sem:
            try:
                detail_html = await client.fetch_html(row["link"])
                detail = parse_detail_fields(detail_html)  # UnexpectedShape propagates
                records[i] = build_listing_record(row, detail)
            except TRANSIENT_ERRORS as e:
                err = extract_error(post_type, "blocked_or_transient", repr(e))
                err["link"] = row.get("link")
                err["id"] = row.get("id")
                records[i] = err

    await asyncio.gather(*(_fetch_one(i, r) for i, r in enumerate(rows)))
    return {"rows": records}


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode") or "all"
        jobs = ["tenders", "disposals", "contracts"] if mode == "all" else [mode]

        max_results = max(1, min(int(input_data.get("maxResultsPerType", 100)), 500))
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = max(1, min(int(input_data.get("maxConcurrency", 5)), 16))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None
        client = NPCClient(proxy_url=proxy_url)

        Actor.log.info(
            f"Running job(s)={jobs}, maxResultsPerType={max_results}, "
            f"fetchDetails={fetch_details}, maxConcurrency={max_concurrency}"
        )

        try:
            for job in jobs:
                if job == "tenders":
                    outcome = await run_tenders_job(client)
                elif job in REST_TYPES:
                    outcome = await run_rest_job(client, job, max_results, fetch_details, max_concurrency)
                else:
                    raise input_error(f"Unknown mode: {job!r}")

                if "error" in outcome:
                    await Actor.push_data(outcome["error"])
                    continue
                await Actor.push_data(outcome["rows"])
        finally:
            await client.close()
