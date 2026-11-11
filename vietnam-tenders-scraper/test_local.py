"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--keyword K] [--dateFrom D] [--dateTo D] [--type T] [--max N]
    python test_local.py detail <inputResultId> [<inputResultId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_list


async def _null_proxy():
    return None


def _opt(args, flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        keyword = _opt(args, "--keyword", "")
        date_from = _opt(args, "--dateFrom")
        date_to = _opt(args, "--dateTo")
        record_type = _opt(args, "--type", "all")
        max_results = int(_opt(args, "--max", "10"))
        records = await run_list(keyword, date_from, date_to, record_type, max_results, _null_proxy)
        print(f"=== list -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        ids = args[1:]
        if not ids:
            print("Usage: python test_local.py detail <inputResultId> [<inputResultId> ...]")
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
