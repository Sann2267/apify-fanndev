"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py search <propertyType> <STATE/City> [maxItems] [fetchDetails(0/1)]
    python test_local.py listing <url> [<url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_listing, run_search


async def run_s(property_type: str, location: str, max_items: int, fetch_details: bool):
    records = await run_search(property_type, location, max_items, fetch_details, 4, None)
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1200], "...")
    sources = {}
    for r in records:
        sources[r.get("_source")] = sources.get(r.get("_source"), 0) + 1
    print(f"\n-> {len(records)} record(s); by _source: {sources}")


async def run_l(urls: list[str]):
    for u in urls:
        record = await run_listing(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2000], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        property_type = sys.argv[2] if len(sys.argv) > 2 else "Houses-For-Rent"
        location = sys.argv[3] if len(sys.argv) > 3 else "TX/Dallas"
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        fetch_details = bool(int(sys.argv[5])) if len(sys.argv) > 5 else True
        asyncio.run(run_s(property_type, location, max_items, fetch_details))
    elif mode == "listing":
        urls = sys.argv[2:] or ["https://www.point2homes.com/US/Home-For-Rent/TX/Dallas/5031-Clover-Haven-Street.html"]
        asyncio.run(run_l(urls))
    else:
        print(__doc__)
        sys.exit(1)
