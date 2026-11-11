"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import COJClient
from src.extractor import NoResultsFound, build_error, build_record


async def run(queries: list[str]):
    for i, query in enumerate(queries):
        if i > 0:
            print("(pausing between queries...)")
            await asyncio.sleep(10)
        client = COJClient()
        try:
            try:
                rows = await client.search(query)
            except NoResultsFound:
                print(json.dumps(build_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row.get("name"), row.get("number"), row.get("status"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:3]:
                record = build_record(query, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps(build_error(query, "blocked_or_transient", repr(e)), ensure_ascii=False))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args))
