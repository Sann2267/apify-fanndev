"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py [--types tenders,awards,intentions,debarments,admin_reviews] [keyword ...] [--max N] [--only-open]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import ALL_LABEL, DEFAULT_NOTICE_TYPES, build_job_records, fetch_notice_rows


async def run(notice_types: list[str], labels: list[str], max_results: int, only_open: bool):
    for notice_type in notice_types:
        rows = await fetch_notice_rows(notice_type, None)
        print(f"=== notice_type={notice_type!r} -> fetched {len(rows)} row(s) from the board ===\n")
        for label in labels:
            records = build_job_records(rows, notice_type, label, only_open, max_results)
            print(f"--- label={label!r} -> {len(records)} record(s) ---")
            for r in records[:5]:
                print(json.dumps(r, ensure_ascii=False, indent=2))
            if len(records) > 5:
                print(f"... and {len(records) - 5} more")
            print()


if __name__ == "__main__":
    args = sys.argv[1:]
    max_results = 100
    only_open = False
    notice_types = list(DEFAULT_NOTICE_TYPES)
    labels = []
    i = 0
    while i < len(args):
        if args[i] == "--max":
            max_results = int(args[i + 1])
            i += 2
        elif args[i] == "--only-open":
            only_open = True
            i += 1
        elif args[i] == "--types":
            notice_types = [t.strip() for t in args[i + 1].split(",") if t.strip()]
            i += 2
        else:
            labels.append(args[i])
            i += 1
    if not labels:
        labels = [ALL_LABEL]
    asyncio.run(run(notice_types, labels, max_results, only_open))
