"""Standalone local runner -- exercises the listing (+ optional detail) flow
without the Apify platform.

Usage:
    python test_local.py <noticeType> [maxItems] [--detail]

    noticeType: tenders | awards | asppa | prequalification | disposals
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import ProcureTTClient
from src.constants import NOTICE_TYPES
from src.extractor import build_error, build_record


async def run(notice_type: str, max_items: int, fetch_detail: bool):
    client = ProcureTTClient()
    try:
        rows, total, page_size = await client.fetch_listing_page(notice_type, 1, None, True)
        print(f"page 1: {len(rows)} rows, upstream total={total}, page_size={page_size}")
        rows = rows[:max_items]

        if fetch_detail and NOTICE_TYPES[notice_type]["has_detail"]:
            for row in rows:
                entry_id = row.get("_entryId")
                row["_detail"] = await client.fetch_detail(notice_type, entry_id) if entry_id else None

        for row in rows[:5]:
            print(" -", json.dumps(row, ensure_ascii=False)[:200])
        if len(rows) > 5:
            print(f"   ... {len(rows) - 5} more")
        print("\n=== full record sample ===")
        source = "S1-html-detail" if fetch_detail else "S1-html-table"
        for row in rows[:2]:
            print(json.dumps(build_record(notice_type, source, row), ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps(build_error(notice_type, "blocked_or_transient", repr(e)), ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    detail_flag = "--detail" in sys.argv[1:]
    if not args or args[0] not in NOTICE_TYPES:
        print(__doc__)
        sys.exit(1)
    notice_type = args[0]
    max_items = int(args[1]) if len(args) > 1 else 10
    asyncio.run(run(notice_type, max_items, detail_flag))
