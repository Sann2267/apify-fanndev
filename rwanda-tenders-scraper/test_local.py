"""Standalone local runner -- exercises list/detail flows without the Apify
platform.

Usage:
    python test_local.py list [maxResults]
    python test_local.py detail <tendReferNo|tendStageCd|tendTypeCd> [...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import UmucyoClient
from src.extractor import build_record, parse_detail, parse_list_page


async def run_list(max_results: int):
    client = UmucyoClient()
    try:
        html = await client.fetch_list_page(1, min(max_results, 50) or 10)
        items, total_results, current_page, total_pages = parse_list_page(html)
        items = items[:max_results]
        print(f"total_results={total_results} page={current_page}/{total_pages}")
        print(f"=== {len(items)} tender notice(s) ===")
        for item in items:
            print(" -", item["tender_no"], "|", item["status"], "|", item["deadline_of_submitting"])
        if items:
            dhtml = await client.fetch_detail(
                *items[0]["detail_ref"].split("|", 2)
            )
            detail = parse_detail(dhtml)
            record = build_record("list", "S1-advertising-list-gu", {**items[0], **detail})
            print("\nSample enriched record:")
            print(json.dumps(record, ensure_ascii=False, indent=2)[:3000])
    finally:
        await client.close()


async def run_detail(refs: list[str]):
    client = UmucyoClient()
    try:
        for ref in refs:
            tend_refer_no, tend_stage_cd, tend_type_cd = ref.split("|", 2)
            html = await client.fetch_detail(tend_refer_no, tend_stage_cd, tend_type_cd)
            detail = parse_detail(html)
            print(f"\n=== {ref} ===")
            print(json.dumps(detail, ensure_ascii=False, indent=2)[:3000])
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    mode = args[0]
    if mode == "list":
        asyncio.run(run_list(int(args[1]) if len(args) > 1 else 10))
    elif mode == "detail":
        if len(args) < 2:
            print(__doc__)
            sys.exit(1)
        asyncio.run(run_detail(args[1:]))
    else:
        print(__doc__)
        sys.exit(1)
