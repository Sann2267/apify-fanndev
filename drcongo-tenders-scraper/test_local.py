"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py [listType] [--max N]

listType defaults to "all". See src/constants.py LIST_CONFIGS for every
valid value (procurement_plan, call_for_tenders, expression_of_interest, ...).
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_list


async def run(args: list[str]):
    list_type = args[0] if args and not args[0].startswith("--") else "all"
    max_results = 50
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])

    records = await run_list(list_type, max_results, None)
    print(f"=== listType={list_type} -> {len(records)} record(s) ===")
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
