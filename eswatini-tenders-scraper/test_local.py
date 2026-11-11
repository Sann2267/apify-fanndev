"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py [tenders|award_intentions|suspended_suppliers] [--max N] [--keyword KW]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_list


async def _null_proxy():
    return None


async def run(args: list[str]):
    list_type = args[0] if args and not args[0].startswith("--") else "tenders"
    max_results = 15
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])
    keyword = ""
    if "--keyword" in args:
        keyword = args[args.index("--keyword") + 1]

    records = await run_list(list_type, max_results, keyword, _null_proxy)
    print(f"=== listType={list_type} keyword={keyword!r} -> {len(records)} record(s) ===")
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    if len(records) > 5:
        print(f"... and {len(records) - 5} more")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
