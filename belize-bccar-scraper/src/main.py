import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BCCARClient
from src.constants import ENTITY_TYPES
from src.extractor import build_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _build_job(raw: str, entity_type: str | None) -> dict:
    """BCCAR's API has genuinely separate `name` and `reg_number` filters
    (confirmed during recon: searching `name` with a registration number's
    digits returns zero matches) -- so a plain string query is routed to
    whichever filter it looks like: all-digits -> `reg_number`, otherwise
    -> `name`. This mirrors what a human using BCCAR's own search form would
    pick for that input.
    """
    filters: dict = {}
    label = raw
    if raw.strip().isdigit():
        filters["reg_number"] = raw.strip()
    else:
        filters["name"] = raw
    if entity_type:
        filters["business_entity_type"] = entity_type
        label = f"{raw} [{ENTITY_TYPES.get(entity_type, entity_type)}]"
    return {"label": label, "filters": filters}


async def run_job(job: dict, max_results: int, proxy_config) -> dict:
    """Runs one search job end-to-end (with internal pagination). Returns
    `{"items": [...], "total": int}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = BCCARClient(proxy_url)
    try:
        items, total = await client.search_all(job["filters"], max_results)
        if not items:
            return {"error": extract_error(job["label"], "not_found")}
        return {"items": items, "total": total}
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": extract_error(job["label"], "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        raw_queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            raw_queries.insert(0, input_data["query"])

        cert_numbers = list(input_data.get("certNumbers") or [])
        entity_type = input_data.get("entityType") or None

        jobs = [_build_job(q, entity_type) for q in raw_queries]
        jobs += [{"label": f"cert:{c}", "filters": {"cert_number": c}} for c in cert_numbers]

        if not jobs and entity_type:
            # Entity-type filter used alone -- list every entity of that type.
            jobs = [{"label": ENTITY_TYPES.get(entity_type, entity_type), "filters": {"business_entity_type": entity_type}}]

        if not jobs:
            raise input_error(
                "Provide 'query'/'queries' (a business name or registration number), "
                "'certNumbers', and/or 'entityType'."
            )

        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 2000)
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_run(job: dict):
            async with sem:
                return await run_job(job, max_results, proxy_config)

        Actor.log.info(f"Running {len(jobs)} search job(s), maxResultsPerQuery={max_results}")
        outcomes = await asyncio.gather(*(_bounded_run(j) for j in jobs))

        for job, outcome in zip(jobs, outcomes):
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                continue
            for entity in outcome["items"]:
                await Actor.push_data(build_record(job["label"], entity))
