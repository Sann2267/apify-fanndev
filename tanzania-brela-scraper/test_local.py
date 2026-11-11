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

from src.client import BRELAClient
from src.extractor import build_error, build_record


async def run(queries: list[str]):
    for query in queries:
        client = BRELAClient()
        try:
            rows = await client.search(query, "any", 50)
            if not rows:
                print(json.dumps(build_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row.get("legal_name"), f"({row.get('cert_number')})", row.get("reg_status_name"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:2]:
                record = build_record(query, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args))
