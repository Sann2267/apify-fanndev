"""Standalone local runner -- exercises the listing flow without the Apify
platform.

Usage:
    python test_local.py opened [maxItems]
    python test_local.py awarded [maxItems]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import GojepClient
from src.extractor import build_error, build_record

SOURCE_BY_TYPE = {
    "opened": "S1-opened-bid-details",
    "awarded": "S2-contract-award-notices",
}


async def run(notice_type: str, max_items: int):
    client = GojepClient()
    fetch_page = client.fetch_opened_page if notice_type == "opened" else client.fetch_awarded_page
    try:
        rows, total = await fetch_page(1)
        print(f"page 1: {len(rows)} rows, upstream total={total}")
        rows = rows[:max_items]
        for row in rows[:5]:
            print(" -", json.dumps(row, ensure_ascii=False)[:200])
        if len(rows) > 5:
            print(f"   ... {len(rows) - 5} more")
        print("\n=== full record sample ===")
        for row in rows[:2]:
            print(json.dumps(build_record(notice_type, SOURCE_BY_TYPE[notice_type], row), ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps(build_error(notice_type, "blocked_or_transient", repr(e)), ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("opened", "awarded"):
        print(__doc__)
        sys.exit(1)
    notice_type = args[0]
    max_items = int(args[1]) if len(args) > 1 else 10
    asyncio.run(run(notice_type, max_items))
