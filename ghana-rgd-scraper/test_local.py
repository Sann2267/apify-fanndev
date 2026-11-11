"""Standalone local runner -- exercises the search without the Apify platform.

Usage:
    python test_local.py <query> [<query> ...] [--type eq|sw|ew|cn] [--max N]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import process_query


async def run(queries: list[str], search_type: str, max_results: int):
    for q in queries:
        records = await process_query(q, search_type, max_results, None)
        print(f"=== query={q!r} type={search_type} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    search_type = "cn"
    max_results = 200
    queries = []
    i = 0
    while i < len(args):
        if args[i] == "--type":
            search_type = args[i + 1]
            i += 2
        elif args[i] == "--max":
            max_results = int(args[i + 1])
            i += 2
        else:
            queries.append(args[i])
            i += 1
    if not queries:
        print("Usage: python test_local.py <query> [<query> ...] [--type eq|sw|ew|cn] [--max N]")
        sys.exit(1)
    asyncio.run(run(queries, search_type, max_results))
