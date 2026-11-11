"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [open|underEvaluation|cancelled|awarded|clarifications|openingRegister|notices|all] [--max N]
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
        list_type = args[1] if len(args) > 1 and not args[1].startswith("--") else "all"
        max_results = 15
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        records = await run_list(list_type, max_results, _null_proxy)
        print(f"=== list type={list_type} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        bid_ids = args[1:]
        if not bid_ids:
            print("Usage: python test_local.py detail <bidId> [<bidId> ...]")
            sys.exit(1)
        records = await run_detail(bid_ids, 3, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
