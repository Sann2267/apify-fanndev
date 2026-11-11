"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py [--max N]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_tenders


async def _null_proxy():
    return None


async def run(args: list[str]):
    max_results = 50
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])

    records = await run_tenders(max_results, _null_proxy)

    print(f"=== {len(records)} record(s) ===")
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
