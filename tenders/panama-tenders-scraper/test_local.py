"""Standalone local runner -- exercises the list/detail flow without the
Apify platform.

Usage:
    python test_local.py list [maxResults]
    python test_local.py detail <ocid>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import PanamaComprasClient
from src.extractor import UnexpectedShape, build_detail_record, build_list_record, parse_record_detail, parse_records_page


async def run_list(max_results: int):
    client = PanamaComprasClient()
    records = []
    next_url = None
    try:
        while len(records) < max_results:
            data = await client.fetch_records_page(next_url)
            page_records, next_url = parse_records_page(data)
            if not page_records:
                break
            records.extend(page_records)
            if not next_url:
                break
    finally:
        await client.close()

    records = records[:max_results]
    print(f"\n=== list -> {len(records)} tender(s), next_cursor={'yes' if next_url else 'no'} ===")
    for r in records[:5]:
        tender = r.get("tender") or {}
        print(" -", r.get("ocid"), "|", tender.get("title"), "|", tender.get("status"))
    if len(records) > 5:
        print(f"   ... {len(records) - 5} more")

    for r in records[:2]:
        record = build_list_record(r, {"startCursor": None})
        print(json.dumps(record, ensure_ascii=False, indent=2))


async def run_detail(ocid: str):
    client = PanamaComprasClient()
    try:
        data = await client.fetch_record(ocid)
        if data is None:
            print(f"not_found: no tender for ocid={ocid!r}")
            return
        try:
            compiled = parse_record_detail(data, ocid)
        except UnexpectedShape as e:
            print(f"UnexpectedShape: {e}")
            return
        record = build_detail_record(ocid, compiled)
        print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        max_results = int(args[1]) if len(args) > 1 else 10
        asyncio.run(run_list(max_results))
    elif args[0] == "detail":
        if len(args) < 2:
            print("Usage: python test_local.py detail <ocid>")
            sys.exit(1)
        asyncio.run(run_detail(args[1]))
    else:
        print(__doc__)
        sys.exit(1)
