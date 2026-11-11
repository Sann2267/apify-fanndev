"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py browse <brand|category> <value> [maxItems]
    python test_local.py listing <id-or-url> [<id-or-url> ...]
    python test_local.py seller <username> [<username> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_browse, run_listing, run_seller


async def run_b(browse_by: str, value: str, max_items: int):
    records = await run_browse(browse_by, value, None, max_items, None)
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:600], "...")
    print(f"\n-> {len(records)} record(s)")


async def run_l(ids: list[str]):
    for i in ids:
        record = await run_listing(i, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_s(usernames: list[str]):
    for u in usernames:
        record = await run_seller(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "browse"
    if mode == "browse":
        browse_by = sys.argv[2] if len(sys.argv) > 2 else "brand"
        value = sys.argv[3] if len(sys.argv) > 3 else "Nike"
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        asyncio.run(run_b(browse_by, value, max_items))
    elif mode == "listing":
        ids = sys.argv[2:] or ["6a8e29a7571a7e204b947d4f"]
        asyncio.run(run_l(ids))
    elif mode == "seller":
        usernames = sys.argv[2:] or ["clarissajohn606"]
        asyncio.run(run_s(usernames))
    else:
        print(__doc__)
        sys.exit(1)
