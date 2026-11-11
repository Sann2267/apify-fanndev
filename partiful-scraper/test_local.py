"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py event <url> [<url> ...]
    python test_local.py host <url> [maxItems]
    python test_local.py discover [region ...] [maxItems]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_discover, run_event, run_host


async def run_ev(urls: list[str]):
    for u in urls:
        record = await run_event(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_hst(url: str, max_items: int):
    records = await run_host(url, max_items, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} record(s)")


async def run_disc(regions: list[str], max_items: int):
    records = await run_discover(regions, max_items, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} event(s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "event"
    if mode == "event":
        urls = sys.argv[2:] or ["S9m7mAA0avBXnFR6rgf0"]
        asyncio.run(run_ev(urls))
    elif mode == "host":
        url = sys.argv[2] if len(sys.argv) > 2 else "gKCLORBCJ02HNuasw3YI"
        max_items = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        asyncio.run(run_hst(url, max_items))
    elif mode == "discover":
        rest = sys.argv[2:]
        max_items = 20
        regions = []
        for tok in rest:
            if tok.isdigit():
                max_items = int(tok)
            else:
                regions.append(tok)
        asyncio.run(run_disc(regions, max_items))
    else:
        print("Usage: python test_local.py [event <url>... | host <url> [maxItems] | discover [region...] [maxItems]]")
        sys.exit(1)
