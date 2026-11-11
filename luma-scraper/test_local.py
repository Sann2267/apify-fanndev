"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py event <url> [<url> ...]
    python test_local.py calendar <url> [period] [maxItems]
    python test_local.py discover [latitude] [longitude] [maxItems]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_calendar, run_discover, run_event


async def run_ev(urls: list[str]):
    for u in urls:
        record = await run_event(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_cal(url: str, period: str, max_items: int):
    records = await run_calendar(url, period, max_items, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} record(s)")


async def run_disc(latitude: str | None, longitude: str | None, max_items: int):
    records = await run_discover(latitude, longitude, max_items, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} event(s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "event"
    if mode == "event":
        urls = sys.argv[2:] or ["sggq2oi9"]
        asyncio.run(run_ev(urls))
    elif mode == "calendar":
        url = sys.argv[2] if len(sys.argv) > 2 else "a16z"
        period = sys.argv[3] if len(sys.argv) > 3 else "future"
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        asyncio.run(run_cal(url, period, max_items))
    elif mode == "discover":
        lat = sys.argv[2] if len(sys.argv) > 2 else None
        lon = sys.argv[3] if len(sys.argv) > 3 else None
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        asyncio.run(run_disc(lat, lon, max_items))
    else:
        print("Usage: python test_local.py [event <url>... | calendar <url> [period] [maxItems] | discover [lat] [lon] [maxItems]]")
        sys.exit(1)
