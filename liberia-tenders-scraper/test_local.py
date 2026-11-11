"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [listType] [--max N]
    python test_local.py detail <resourceId> [<resourceId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_list


async def _noop_proxy():
    return None


async def run(mode: str, args: list[str]):
    if mode == "list":
        list_type = "current"
        max_results = 20
        rest = list(args)
        if rest and rest[0] in ("current", "opened", "awarded"):
            list_type = rest.pop(0)
        if rest and rest[0] == "--max":
            max_results = int(rest[1])
        records = await run_list(list_type, max_results, _noop_proxy)
        print(f"=== listType={list_type!r} -> {len(records)} record(s) ===\n")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")
    elif mode == "detail":
        if not args:
            print("Provide at least one resourceId.")
            return
        records = await run_detail(args, 3, _noop_proxy)
        print(f"=== {len(records)} detail record(s) ===\n")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"Unknown mode {mode!r}. Use 'list' or 'detail'.")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        argv = ["list"]
    asyncio.run(run(argv[0], argv[1:]))
