"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py latest [--max N]
    python test_local.py archived [--max N]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_archived, run_latest


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    mode = args[0]
    max_results = 15
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])

    if mode == "latest":
        records = await run_latest(max_results, _null_proxy)
    elif mode == "archived":
        records = await run_archived(max_results, _null_proxy)
    else:
        print(__doc__)
        sys.exit(1)

    print(f"=== mode={mode} -> {len(records)} record(s) ===")
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    if len(records) > 5:
        print(f"... and {len(records) - 5} more")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
