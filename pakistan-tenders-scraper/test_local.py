"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--listingType active|history] [--keyword TEXT] [--category CAT]
                               [--sector SEC] [--type TYPE] [--nature NAT] [--status ST] [--max N]
    python test_local.py detail <tenderNo> [<tenderNo> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_list


async def _null_proxy():
    return None


def _opt(args: list[str], flag: str, default=None):
    return args[args.index(flag) + 1] if flag in args else default


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        input_data = {
            "listingType": _opt(args, "--listingType", "active"),
            "keyword": _opt(args, "--keyword", ""),
            "procurementCategory": _opt(args, "--category", "all"),
            "sector": _opt(args, "--sector", "all"),
            "tenderType": _opt(args, "--type", "all"),
            "tenderNature": _opt(args, "--nature", "all"),
            "status": _opt(args, "--status", "all"),
            "maxResults": int(_opt(args, "--max", "15")),
        }
        records = await run_list(input_data, _null_proxy)
        print(f"=== list {input_data} -> {len(records)} record(s) ===")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        tender_nos = args[1:]
        if not tender_nos:
            print("Usage: python test_local.py detail <tenderNo> [<tenderNo> ...]")
            sys.exit(1)
        records = await run_detail(tender_nos, 3, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
