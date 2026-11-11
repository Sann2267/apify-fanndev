"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py search <keyword> [maxResults] [fetchFullDetails: 0|1]
    python test_local.py detail <id-or-url> [<id-or-url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_search


async def _no_proxy():
    return None


async def run_s(keyword: str, max_results: int, fetch_full_details: bool):
    records = await run_search(keyword, None, {}, max_results, fetch_full_details, 4, _no_proxy)
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} record(s)")


async def run_d(ids: list[str]):
    for i in ids:
        record = await run_detail(i, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else "marketing"
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        fetch_full_details = bool(int(sys.argv[4])) if len(sys.argv) > 4 else True
        asyncio.run(run_s(keyword, max_results, fetch_full_details))
    elif mode == "detail":
        ids = sys.argv[2:] or ["1401468"]
        asyncio.run(run_d(ids))
    else:
        print(__doc__)
        sys.exit(1)
