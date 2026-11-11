"""Mode dispatch for the Himalayas remote-jobs Actor.

Four modes over one endpoint:

* ``jobs``      -- walk the feed newest-first and emit every job.
* ``search``    -- the same walk with **local** filtering, because the upstream
  API accepts filter parameters and ignores all of them.
* ``companies`` -- the same walk collapsed to one record per company, a hiring
  volume view that costs no extra requests.
* ``reference`` -- probe the feed and report measurable evidence, including a
  live re-test of the two limits this Actor is designed around.
"""

import logging
from datetime import datetime, timezone

from apify import Actor

from src.client import FeedUnavailable, HimalayasClient
from src.constants import (
    FILTER_FIELDS,
    MAX_PAGES,
    MODES,
    PAGE_LIMIT,
    URL_JOBS,
)
from src.extractor import (
    aggregate_companies,
    extract_error,
    matches,
    normalize_job,
    wrap_reference,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

RECORD_TYPES = {
    "himalayas-jobs-api": "JOB",
    "reference": "SURFACE",
    "error": "ERROR",
}


def envelope(record: dict, input_value: str, record_type: str | None = None) -> dict:
    """The portfolio's mandatory meta fields (.ai/conventions/dataset-envelope.md)."""
    record.setdefault("_input", input_value)
    record.setdefault("_source", "none")
    record["_scrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_source = RECORD_TYPES.get(record["_source"])
    record.setdefault(
        "recordType",
        by_source if by_source in ("SURFACE", "ERROR") else (record_type or by_source or "JOB"),
    )
    return record


async def walk_feed(
    client: HimalayasClient,
    max_items: int,
    filters: dict | None,
    max_scanned: int,
    on_page=None,
) -> tuple[list[dict], dict]:
    """Walk the cursor until ``max_items`` matches are collected.

    ``max_scanned`` is the safety valve that a filtered run needs: filtering is
    local, so a narrow filter over 97,000 jobs would otherwise walk the entire
    feed 20 jobs at a time. The run stops at that scan budget and reports how
    far it got, rather than silently costing 4,850 requests.
    """
    collected: list[dict] = []
    cursor: str | None = None
    scanned = 0
    pages = 0
    stats = {"scanned": 0, "pages": 0, "totalCount": None, "stopReason": None, "feedUpdatedAt": None}

    while len(collected) < max_items and pages < MAX_PAGES:
        url = f"{URL_JOBS}?limit={PAGE_LIMIT}" + (f"&cursor={cursor}" if cursor else "")
        payload = await client.get_json(url)
        pages += 1

        if stats["totalCount"] is None:
            stats["totalCount"] = payload.get("totalCount")
            stats["feedUpdatedAt"] = payload.get("updatedAt")

        jobs = payload.get("jobs") or []
        if not jobs:
            stats["stopReason"] = "feed_exhausted"
            break

        for raw in jobs:
            scanned += 1
            record = normalize_job(raw)
            if filters and not matches(record, filters):
                continue
            collected.append(record)
            if len(collected) >= max_items:
                break

        if on_page:
            on_page(pages, scanned, len(collected))

        cursor = payload.get("nextCursor")
        if not cursor:
            stats["stopReason"] = "no_more_cursors"
            break
        if scanned >= max_scanned:
            stats["stopReason"] = "scan_budget_reached"
            break

    stats["scanned"] = scanned
    stats["pages"] = pages
    stats["stopReason"] = stats["stopReason"] or "max_items_reached"
    return collected, stats


def collect_filters(input_data: dict) -> dict:
    filters: dict = {}
    for key in FILTER_FIELDS:
        value = input_data.get(key)
        if value not in (None, "", [], {}):
            filters[key] = value
    for key in ("minSalary", "maxSalary"):
        if input_data.get(key) is not None:
            filters[key] = int(input_data[key])
    if input_data.get("currency"):
        filters["currency"] = input_data["currency"]
    if input_data.get("salariedOnly"):
        filters["salariedOnly"] = True
    return filters


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe the feed and re-test the two limits this Actor is designed around.

    Both are behaviours that would be invisible in a normal run: a page cap
    that silently truncates, and filter parameters that are accepted and
    ignored. Re-testing them here means a change upstream shows up as a
    reference-mode diff instead of as quietly wrong data.
    """
    client = HimalayasClient(proxy_url=proxy_url)
    url = f"{URL_JOBS}?limit=1"
    try:
        payload = await client.get_json(url)
        jobs = payload.get("jobs") or []

        # Limit cap: ask for 100, count what comes back.
        big = await client.get_json(f"{URL_JOBS}?limit=100")
        cap = len(big.get("jobs") or [])

        # Filter honesty: ask for an implausible slice and see if it changed.
        unfiltered = await client.get_json(f"{URL_JOBS}?limit=3")
        filtered = await client.get_json(f"{URL_JOBS}?limit=3&categories=Design&minSalary=900000")
        server_side_filtering = [j.get("guid") for j in unfiltered.get("jobs", [])] != [
            j.get("guid") for j in filtered.get("jobs", [])
        ]

        sample = {
            "totalCount": payload.get("totalCount"),
            "feedUpdatedAt": payload.get("updatedAt"),
            "cursorPaginationAvailable": bool(payload.get("nextCursor")),
            "jobsReturnedForLimit100": cap,
            "pageLimitThisActorUses": PAGE_LIMIT,
            "serverSideFilteringWorks": server_side_filtering,
            "sampleTitle": jobs[0].get("title") if jobs else None,
            "sampleCompany": jobs[0].get("companyName") if jobs else None,
            "feedComments": str(payload.get("comments"))[:240],
        }
        note = "payload parsed" if jobs else "200 but no jobs in the feed"
        if server_side_filtering:
            note += (
                " -- NOTE: the feed appears to filter server-side now, which it did not on "
                "2026-09-18. Local filtering still returns correct results, but the scan "
                "budget could be relaxed if this holds."
            )
        return [wrap_reference(url, bool(jobs), note, sample)]
    except Exception as exc:  # noqa: BLE001 -- a probe reports, it never raises
        return [wrap_reference(url, False, repr(exc))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "jobs")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 100))
        max_scanned = int(input_data.get("maxScannedJobs", 2000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict], input_value: str, record_type: str | None = None):
            if records:
                await Actor.push_data([envelope(r, input_value, record_type) for r in records])

        if mode == "reference":
            records = await run_reference(proxy_url)
            Actor.log.info(
                f"mode=reference: available={records[0].get('isAvailable')} {records[0].get('sample')}"
            )
            await push(records, "reference")
            return

        filters = collect_filters(input_data) if mode == "search" else {}
        if mode == "search" and not filters:
            raise input_error(
                "Mode 'search' needs at least one filter, e.g. 'titleContains', "
                "'categories', 'seniority', 'locationRestrictions', 'currency' or "
                "'minSalary'. "
                "For the unfiltered feed use mode 'jobs'."
            )

        # In companies mode the interesting output is the aggregate, so the
        # item budget applies to companies while jobs are gathered up to the
        # scan budget.
        job_budget = max_scanned if mode == "companies" else max_items

        client = HimalayasClient(proxy_url=proxy_url)
        try:
            def progress(pages: int, scanned: int, kept: int):
                Actor.log.info(f"page {pages}: scanned {scanned}, kept {kept}")

            jobs, stats = await walk_feed(client, job_budget, filters, max_scanned, progress)
        except FeedUnavailable as exc:
            await push([extract_error(mode, "feed_unavailable", str(exc))], mode)
            return
        finally:
            await client.close()

        Actor.log.info(
            f"mode={mode}: {stats['pages']} page(s), scanned {stats['scanned']}, "
            f"matched {len(jobs)}, feed totalCount={stats['totalCount']}, "
            f"stopped because {stats['stopReason']}"
        )

        if mode == "companies":
            companies = aggregate_companies(jobs)[:max_items]
            for company in companies:
                company["jobsScannedInRun"] = stats["scanned"]
            await push(companies, mode, "COMPANY")
            Actor.log.info(f"mode=companies -> {len(companies)} company record(s)")
            return

        if not jobs and filters:
            await push(
                [
                    extract_error(
                        mode,
                        "no_matches",
                        f"scanned {stats['scanned']} of {stats['totalCount']} jobs and none "
                        f"matched the filters; stopped because {stats['stopReason']}. Raise "
                        f"'maxScannedJobs' or widen the filters.",
                    )
                ],
                mode,
            )
            return

        for job in jobs:
            job["jobsScannedInRun"] = stats["scanned"]
        await push(jobs, mode, "JOB")
        Actor.log.info(f"mode={mode} -> {len(jobs)} job record(s)")
