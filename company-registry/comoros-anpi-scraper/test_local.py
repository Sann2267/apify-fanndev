"""Standalone local runner -- exercises the ANPI directory search/browse
flow without the Apify platform.

Usage:
    python test_local.py <search term> [<search term> ...]
    python test_local.py --browse [island] [year]   # no free-text search
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import describe_job, run_one_job
from src.extractor import build_record, extract_error


async def run(jobs: list[dict], max_results: int):
    for filters in jobs:
        label = describe_job(filters)
        outcome = await run_one_job(filters, max_results, max_concurrency=4, proxy_config=None)
        if "error" in outcome:
            print(json.dumps(extract_error(label, outcome["error"], outcome.get("detail")), ensure_ascii=False))
            continue
        print(f"\n=== {label!r} -> {outcome['total']} total on file, showing {len(outcome['rows'])} ===")
        for row in outcome["rows"][:5]:
            print(" -", row.get("nom"), "|", row.get("ile"), "|", row.get("annee"), "|", row.get("siege"))
        if len(outcome["rows"]) > 5:
            print(f"   ... {len(outcome['rows']) - 5} more")
        if outcome["rows"]:
            record = build_record(label, outcome["rows"][0])
            print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--browse":
        rest = args[1:]
        filters = {"search": None, "ile": rest[0] if len(rest) > 0 else None,
                   "annee": rest[1] if len(rest) > 1 else None, "secteur": None, "siege": None, "rccm": None}
        asyncio.run(run([filters], max_results=10))
    else:
        jobs = [{"search": q, "ile": None, "secteur": None, "annee": None, "siege": None, "rccm": None} for q in args]
        asyncio.run(run(jobs, max_results=10))
