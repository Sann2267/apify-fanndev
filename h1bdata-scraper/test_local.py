"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py search <employer> [jobTitle] [city] [year] [maxResults] [fetchCaseDetails(0/1)]
    python test_local.py caseDetail <caseId> [<caseId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_case_detail, run_search


async def run_s(employer: str, job_title: str, city: str, year: str, max_results: int, fetch_case_details: bool):
    records = await run_search(employer, job_title, city, year, max_results, fetch_case_details, 4, None)
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1500], "...")
    sources = {}
    for r in records:
        sources[r.get("_source")] = sources.get(r.get("_source"), 0) + 1
    print(f"\n-> {len(records)} record(s); by _source: {sources}")


async def run_c(case_ids: list[str]):
    for cid in case_ids:
        record = await run_case_detail(cid, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        employer = sys.argv[2] if len(sys.argv) > 2 else "Google"
        job_title = sys.argv[3] if len(sys.argv) > 3 else ""
        city = sys.argv[4] if len(sys.argv) > 4 else ""
        year = sys.argv[5] if len(sys.argv) > 5 else "2024"
        max_results = int(sys.argv[6]) if len(sys.argv) > 6 else 10
        fetch_case_details = bool(int(sys.argv[7])) if len(sys.argv) > 7 else False
        asyncio.run(run_s(employer, job_title, city, year, max_results, fetch_case_details))
    elif mode == "caseDetail":
        case_ids = sys.argv[2:] or ["I-200-21027-037298"]
        asyncio.run(run_c(case_ids))
    else:
        print(__doc__)
        sys.exit(1)
