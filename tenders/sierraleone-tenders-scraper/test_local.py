"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py [keyword ...] [--max N] [--only-open]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import ALL_LABEL, build_job_records, fetch_all_rows


async def run(labels: list[str], max_results: int, only_open: bool):
    rows = await fetch_all_rows(None)
    print(f"=== fetched {len(rows)} tender row(s) from the board ===\n")
    for label in labels:
        records = build_job_records(rows, label, only_open, max_results)
        print(f"=== label={label!r} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    max_results = 100
    only_open = False
    labels = []
    i = 0
    while i < len(args):
        if args[i] == "--max":
            max_results = int(args[i + 1])
            i += 2
        elif args[i] == "--only-open":
            only_open = True
            i += 1
        else:
            labels.append(args[i])
            i += 1
    if not labels:
        labels = [ALL_LABEL]
    asyncio.run(run(labels, max_results, only_open))
