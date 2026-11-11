"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--open-only] [--keyword TEXT] [--max N]
    python test_local.py detail <bidId> [<bidId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_list


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        open_only = "--open-only" in args
        keyword = None
        if "--keyword" in args:
            keyword = args[args.index("--keyword") + 1]
        max_results = 10
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        records = await run_list(open_only, keyword, max_results, _null_proxy)
        print(f"=== list openOnly={open_only} keyword={keyword!r} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        bid_ids = args[1:]
        if not bid_ids:
            print("Usage: python test_local.py detail <bidId> [<bidId> ...]")
            sys.exit(1)
        records = await run_detail(bid_ids, 2, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
