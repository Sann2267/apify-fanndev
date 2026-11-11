"""Standalone local runner -- exercises the crawl flow without the Apify platform.

Usage:
    python test_local.py latest [maxItems]
    python test_local.py list [maxItems]
    python test_local.py detail <lotId> [<lotId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail_one, run_listing


async def run(args: list[str]):
    mode = args[0] if args else "latest"

    if mode == "latest":
        max_items = int(args[1]) if len(args) > 1 else 5
        records = await run_listing(None, "latest", max_items, None)
    elif mode == "list":
        max_items = int(args[1]) if len(args) > 1 else 15
        records = await run_listing(None, "list", max_items, None)
    elif mode == "detail":
        targets = args[1:] or ["29208ca2-a834-4bb5-80cf-95d2dc62a057"]
        records = await asyncio.gather(*(run_detail_one(t, None) for t in targets))
    else:
        print(f"Unknown mode {mode!r}")
        return

    for record in records:
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2500])
    print(f"-> mode={mode!r} records={len(records)}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
