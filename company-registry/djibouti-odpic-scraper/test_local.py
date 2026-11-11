"""Standalone local runner -- exercises the search/browse flow without the
Apify platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --latest [<max_results>]   # browse newest filings, no name filter
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import ODPICClient
from src.extractor import build_record, extract_error


async def run_query(query: str | None, max_results: int = 5):
    label = query if query else "(latest)"
    client = ODPICClient()
    try:
        filters = {"search": query, "orderby": "date", "order": "desc"}
        rows, total = await client.fetch_page(filters, page=1, per_page=max_results)
        print(f"\n=== {label!r} -> total={total}, showing {len(rows)} ===")
        if not rows:
            print(json.dumps(extract_error(label, "not_found"), ensure_ascii=False))
            return
        for row in rows:
            record = build_record(label, row)
            print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


async def run_all(queries: list[str]):
    for q in queries:
        await run_query(q)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--latest":
        n = int(args[1]) if len(args) > 1 else 5
        asyncio.run(run_query(None, n))
    else:
        asyncio.run(run_all(args))
