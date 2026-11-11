"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--year Y --month M] [--max N] [--detail]
    python test_local.py detail <idCompra> [<idCompra> ...]
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
        year = None
        if "--year" in args:
            year = int(args[args.index("--year") + 1])
        month = None
        if "--month" in args:
            month = int(args[args.index("--month") + 1])
        max_results = 10
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        fetch_detail = "--detail" in args
        records = await run_list(year, month, max_results, fetch_detail, _null_proxy)
        print(f"=== list year={year} month={month} fetchDetail={fetch_detail} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        ids = [int(a) for a in args[1:]]
        if not ids:
            print("Usage: python test_local.py detail <idCompra> [<idCompra> ...]")
            sys.exit(1)
        records = await run_detail(ids, 2, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
