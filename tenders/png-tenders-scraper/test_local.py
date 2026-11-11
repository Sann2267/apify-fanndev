"""Standalone local runner -- exercises each mode without the Apify platform.

Usage:
    python test_local.py tenders
    python test_local.py disposals [max_results] [fetch_details=1|0]
    python test_local.py contracts [max_results] [fetch_details=1|0]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import NPCClient
from src.constants import BASE_URL, PER_PAGE, TENDER_ADVERTISEMENT_PATH
from src.extractor import (
    build_listing_record,
    build_tender_record,
    extract_error,
    flatten_rest_row,
    parse_detail_fields,
    parse_tender_cards,
)


async def run_tenders():
    client = NPCClient()
    try:
        url = f"{BASE_URL}{TENDER_ADVERTISEMENT_PATH}"
        page_html = await client.fetch_html(url)
        cards = parse_tender_cards(page_html)
        print(f"=== tenders -> {len(cards)} open tender(s) ===")
        if not cards:
            print(json.dumps(extract_error("tenders", "not_found"), ensure_ascii=False))
            return
        for c in cards:
            print(json.dumps(build_tender_record(c, url), ensure_ascii=False, indent=2))
    finally:
        await client.close()


async def run_rest(record_type: str, max_results: int, fetch_details: bool):
    from src.constants import REST_TYPES

    post_type = REST_TYPES[record_type]
    client = NPCClient()
    try:
        page_rows, total = await client.fetch_rest_page(post_type, page=1, per_page=min(max_results, PER_PAGE))
        rows = [flatten_rest_row(r, post_type) for r in page_rows][:max_results]
        print(f"=== {record_type} -> total={total}, showing {len(rows)} ===")
        if not rows:
            print(json.dumps(extract_error(post_type, "not_found"), ensure_ascii=False))
            return
        for row in rows:
            detail = None
            if fetch_details:
                detail_html = await client.fetch_html(row["link"])
                detail = parse_detail_fields(detail_html)
            print(json.dumps(build_listing_record(row, detail), ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    mode = args[0]
    if mode == "tenders":
        asyncio.run(run_tenders())
    elif mode in ("disposals", "contracts"):
        n = int(args[1]) if len(args) > 1 else 5
        details = bool(int(args[2])) if len(args) > 2 else True
        asyncio.run(run_rest(mode, n, details))
    else:
        print(__doc__)
        sys.exit(1)
