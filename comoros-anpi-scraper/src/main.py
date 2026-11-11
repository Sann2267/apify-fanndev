import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ANPIClient
from src.constants import MAX_PAGES_PER_JOB, PER_PAGE
from src.extractor import UnexpectedShape, build_record, extract_error

log = logging.getLogger(__name__)


def describe_job(filters: dict) -> str:
    """Human-readable label for `_input` when a job has no free-text search
    term -- e.g. a pure filter browse ('island=anjouan, year=2024') or the
    full-directory browse ('(all companies)') when no filter is set at all.
    """
    if filters.get("search"):
        return filters["search"]
    parts = []
    if filters.get("ile"):
        parts.append(f"island={filters['ile']}")
    if filters.get("secteur"):
        parts.append(f"sector={filters['secteur']}")
    if filters.get("annee"):
        parts.append(f"year={filters['annee']}")
    if filters.get("siege"):
        parts.append(f"city={filters['siege']}")
    if filters.get("rccm"):
        parts.append(f"rccm={filters['rccm']}")
    return ", ".join(parts) if parts else "(all companies)"


async def run_one_job(filters: dict, max_results: int, max_concurrency: int, proxy_config) -> dict:
    """Runs one filtered listing end-to-end. The API returns `total`/`pages`
    up front, so this fetches only the pages actually needed to satisfy
    `max_results` (not blind page-by-page crawling). Returns
    `{"rows": [...], "total": int, "truncated": bool}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ANPIClient(proxy_url)
    try:
        first = await client.fetch_page(filters, page=1)
        total = int(first.get("total") or 0)
        if total == 0:
            return {"error": "no_results"}

        rows = list(first.get("data") or [])
        needed = min(total, max_results)
        pages_wanted = -(-needed // PER_PAGE)  # ceil division
        pages_to_fetch = min(pages_wanted, MAX_PAGES_PER_JOB)
        truncated = pages_wanted > pages_to_fetch

        if pages_to_fetch > 1:
            sem = asyncio.Semaphore(max_concurrency)

            async def _fetch(p: int):
                async with sem:
                    page = await client.fetch_page(filters, page=p)
                    return page.get("data") or []

            results = await asyncio.gather(*(_fetch(p) for p in range(2, pages_to_fetch + 1)))
            for page_rows in results:
                rows.extend(page_rows)

        return {"rows": rows[:needed], "total": total, "truncated": truncated}
    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": "blocked_or_transient", "detail": repr(e)}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        query_terms = list(input_data.get("queries") or [])
        if input_data.get("query"):
            query_terms.insert(0, input_data["query"])

        island = (input_data.get("island") or "any").strip()
        sector = (input_data.get("sector") or "any").strip()
        year = str(input_data.get("year") or "").strip()
        city = (input_data.get("city") or "").strip()
        rccm = (input_data.get("rccm") or "").strip()

        shared_filters = {
            "ile": island if island != "any" else None,
            "secteur": sector if sector != "any" else None,
            "annee": year or None,
            "siege": city or None,
            "rccm": rccm or None,
        }

        max_results = min(int(input_data.get("maxResultsPerQuery", 200)), 6400)
        max_concurrency = max(1, int(input_data.get("maxConcurrency", 4)))

        if query_terms:
            jobs = [{**shared_filters, "search": q} for q in query_terms]
        else:
            # No free-text term at all: run a single job on the shared
            # filters alone (or, if none of those are set either, this
            # browses the entire public directory up to max_results).
            jobs = [{**shared_filters, "search": None}]

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        job_sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(filters: dict):
            async with job_sem:
                return await run_one_job(filters, max_results, max_concurrency, proxy_config)

        Actor.log.info(
            f"Running {len(jobs)} job(s) against ANPI's Annuaire des entreprises "
            f"(maxResultsPerQuery={max_results}, maxConcurrency={max_concurrency})"
        )
        outcomes = await asyncio.gather(*(_bounded(f) for f in jobs))

        for filters, outcome in zip(jobs, outcomes):
            label = describe_job(filters)
            if "error" in outcome:
                await Actor.push_data(extract_error(label, outcome["error"], outcome.get("detail")))
                continue
            warning = "pagination_truncated_by_page_cap" if outcome.get("truncated") else None
            Actor.log.info(f"{label!r}: {outcome['total']} total match(es) on file, {len(outcome['rows'])} returned")
            for row in outcome["rows"]:
                record = build_record(label, row)
                if warning:
                    record["_warning"] = warning
                await Actor.push_data(record)
