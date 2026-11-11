"""Local smoke test: run every mode against live Glints without the Apify SDK.

    python test_local.py            # all modes
    python test_local.py search     # one mode

Exercises the same client and mode coroutines main.py uses, so a pass here
means the only untested surface left is the Actor wrapper itself.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from src.client import GlintsClient
from src.modes import MODES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)

# A real Glints posting and its employer, resolved at runtime from a search so
# the fixtures cannot rot when the posting closes.
SEED_TERM = "data analyst"

CASES: dict[str, dict[str, Any]] = {
    "search": {
        "countryCode": "ID",
        "searchTerms": ["data analyst", "content writer"],
        "maxItems": 60,
        "pageSize": 50,
    },
    "jobDetail": {"countryCode": "ID", "jobUrlsOrIds": []},  # filled from seed
    "company": {"countryCode": "ID", "companyUrlsOrIds": []},  # filled from seed
    "similarJobs": {"countryCode": "ID", "jobUrlsOrIds": [], "similarJobsLimit": 10},
    "sitemapCrawl": {
        "countryCode": "ID",
        "maxItems": 6,
        "maxConcurrency": 3,
        "sitemapFetchDetails": True,
    },
    "filters": {"countryCode": "ID", "searchTerms": ["data analyst"], "facetLimit": 10},
    "suggestions": {"countryCode": "ID", "searchTerms": ["data"], "suggestionLimit": 15},
    "skills": {"countryCode": "ID", "searchTerms": ["python"], "maxItems": 10},
}


async def collect(client: GlintsClient, mode: str, inp: dict[str, Any]) -> list[dict[str, Any]]:
    return [record async for record in MODES[mode](client, inp)]


def summarise(mode: str, rows: list[dict[str, Any]]) -> bool:
    errors = [r for r in rows if r.get("_error")]
    good = [r for r in rows if not r.get("_error")]
    types: dict[str, int] = {}
    for r in rows:
        types[r.get("recordType", "?")] = types.get(r.get("recordType", "?"), 0) + 1

    print(f"\n{'=' * 78}\nMODE {mode}: {len(rows)} rows ({len(good)} data, {len(errors)} error)")
    print(f"  recordTypes: {types}")
    for err in errors[:3]:
        print(f"  ERROR row: {err.get('_error')} :: {str(err.get('_errorDetail'))[:140]}")

    if good:
        sample = good[0]
        envelope_ok = all(k in sample for k in ("_input", "_source", "_scrapedAt", "recordType"))
        print(f"  envelope complete: {envelope_ok}")
        preview = {
            k: (v[:90] + "..." if isinstance(v, str) and len(v) > 90 else v)
            for k, v in sample.items()
            if k in (
                "_source", "recordType", "id", "title", "companyName", "locationName",
                "salaryMin", "salaryMax", "salaryCurrency", "salaryMode", "jobUrl",
                "categoryPath", "skillNames", "name", "jobCount", "suggestion",
                "suggestionType", "skillName", "skillId", "topCompanyNames",
            )
        }
        print("  sample:", json.dumps(preview, ensure_ascii=False, default=str)[:700])
        if mode in ("jobDetail", "sitemapCrawl"):
            desc = sample.get("descriptionText") or ""
            print(f"  descriptionText: {len(desc)} chars -> {desc[:120]!r}")
            print(f"  benefits: {sample.get('benefitTitles')}")
        if not envelope_ok:
            return False
    return bool(good)


async def resolve_seeds(client: GlintsClient) -> tuple[str, str]:
    """Find a live job id and company id so the detail modes test real targets."""
    rows = await collect(
        client, "search", {"countryCode": "ID", "searchTerms": [SEED_TERM], "maxItems": 5}
    )
    jobs = [r for r in rows if r.get("id") and not r.get("_error")]
    if not jobs:
        raise RuntimeError("Could not seed test fixtures: search returned no jobs")
    job = jobs[0]
    company_id = (job.get("company") or {}).get("id")
    print(f"Seeded from live search: job={job['id']} ({job.get('title')}) company={company_id}")
    return job["id"], company_id


async def main() -> int:
    wanted = sys.argv[1:] or list(CASES)
    client = GlintsClient(country_code="ID")
    results: dict[str, bool] = {}
    try:
        job_id, company_id = await resolve_seeds(client)
        CASES["jobDetail"]["jobUrlsOrIds"] = [job_id]
        CASES["similarJobs"]["jobUrlsOrIds"] = [job_id]
        CASES["company"]["companyUrlsOrIds"] = [company_id] if company_id else []

        for mode in wanted:
            if mode not in CASES:
                print(f"Unknown mode {mode}")
                continue
            try:
                rows = await collect(client, mode, CASES[mode])
                results[mode] = summarise(mode, rows)
            except Exception as exc:  # noqa: BLE001 - report, keep testing
                logging.exception("Mode %s raised", mode)
                results[mode] = False
                print(f"\nMODE {mode}: RAISED {type(exc).__name__}: {exc}")
    finally:
        client.close()

    print(f"\n{'=' * 78}\nSUMMARY")
    for mode, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {mode}")
    failed = [m for m, ok in results.items() if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} modes passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
