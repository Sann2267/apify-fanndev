"""Standalone local runner -- exercises the name-search flow without the
Apify platform.

Usage:
    python test_local.py <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import URSBClient
from src.extractor import build_record, extract_error


async def run(queries: list[str]):
    for query in queries:
        client = URSBClient()
        try:
            items, truncated = await client.search_all(query, max_results=20)
            if not items:
                print(json.dumps(extract_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(items)} match(es) (truncated={truncated}) ===")
            for entity in items[:5]:
                print(" -", entity.get("name"), entity.get("ern"), entity.get("type"), entity.get("status"))
            if len(items) > 5:
                print(f"   ... {len(items) - 5} more")
            record = build_record(query, items[0], truncated)
            print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args))
