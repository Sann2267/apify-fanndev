"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --mode directors <surname>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import ROCIPClient
from src.extractor import build_error, build_record


async def run(queries: list[str], mode: str):
    for query in queries:
        client = ROCIPClient()
        try:
            rows = await client.search(query, mode, 50)
            if not rows:
                print(json.dumps(build_error(query, mode, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} (mode={mode}) -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row.get("EntityName"), f"({row.get('EntityNumber')})", row.get("StatusName"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:2]:
                record = build_record(query, mode, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = "entities"
    if args[:1] == ["--mode"]:
        mode = args[1]
        args = args[2:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, mode))
