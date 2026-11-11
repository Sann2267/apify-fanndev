"""Standalone local runner -- exercises the search flow without the Apify platform.

Usage:
    python test_local.py <company name> [<company name> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import search_company


async def run(queries: list[str]):
    for q in queries:
        records = await search_company(q, None)
        for record in records:
            print(json.dumps(record, ensure_ascii=False, indent=2)[:1500])
        print(f"-> query={q!r} records={len(records)}")


if __name__ == "__main__":
    queries = sys.argv[1:]
    if not queries:
        queries = ["Zambia Sugar"]
    asyncio.run(run(queries))
