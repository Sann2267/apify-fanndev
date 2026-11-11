"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py latest [--max N]
    python test_local.py archive [--start-page N] [--max N]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_archive, run_latest


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    max_results = 15
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])

    if args[0] == "latest":
        records = await run_latest(max_results, _null_proxy)
        print(f"=== latest -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "archive":
        start_page = 1
        if "--start-page" in args:
            start_page = int(args[args.index("--start-page") + 1])
        records = await run_archive(start_page, max_results, _null_proxy)
        print(f"=== archive startPage={start_page} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
