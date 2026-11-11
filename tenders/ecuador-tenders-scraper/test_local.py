"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list --year 2020 --search KEYWORD [--buyer X] [--supplier Y] [--max N] [--detail]
    python test_local.py detail <ocid> [<ocid> ...]
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
        year = 2020
        if "--year" in args:
            year = int(args[args.index("--year") + 1])
        search = ""
        if "--search" in args:
            search = args[args.index("--search") + 1]
        buyer = ""
        if "--buyer" in args:
            buyer = args[args.index("--buyer") + 1]
        supplier = ""
        if "--supplier" in args:
            supplier = args[args.index("--supplier") + 1]
        max_results = 10
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        fetch_detail = "--detail" in args
        records = await run_list(year, search, max_results, buyer, supplier, fetch_detail, _null_proxy)
        print(f"=== list year={year} search={search!r} fetchDetail={fetch_detail} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        ocids = args[1:]
        if not ocids:
            print("Usage: python test_local.py detail <ocid> [<ocid> ...]")
            sys.exit(1)
        records = await run_detail(ocids, 2, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
