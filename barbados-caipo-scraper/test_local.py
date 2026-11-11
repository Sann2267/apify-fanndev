"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <name-query> [<name-query> ...]
    python test_local.py --number <registration-number> [<number> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import CAIPOClient
from src.extractor import SearchApiError, build_error, build_record


async def run(queries: list[str], search_field: str):
    for query in queries:
        client = CAIPOClient()
        try:
            name = query if search_field == "name" else None
            number = query if search_field == "number" else None
            try:
                rows, total, truncated = await client.search(name=name, number=number)
            except SearchApiError as e:
                print(json.dumps(build_error(query, "search_api_error", str(e)), ensure_ascii=False))
                continue
            if not rows:
                print(json.dumps(build_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {total} total match(es) (truncated={truncated}) ===")
            for row in rows[:5]:
                print(" -", row.get("company_name"), row.get("company_number"), row.get("registration_category"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:2]:
                record = build_record(query, row, total, truncated)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    search_field = "name"
    if args and args[0] == "--number":
        search_field = "number"
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, search_field))
