"""Standalone local runner -- exercises latest/archived/detail flows without
the Apify platform.

Usage:
    python test_local.py latest [maxResults]
    python test_local.py archived [maxResults] [financialYear]
    python test_local.py detail <notice_id_or_url> [<notice_id_or_url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import EGPUgandaClient
from src.extractor import (
    build_record,
    clean_archived_record,
    parse_bid_opening_detail,
    parse_latest_open_notices,
    parse_notice_detail,
)


async def run_latest(max_results: int):
    client = EGPUgandaClient()
    try:
        html = await client.fetch_bid_notices_page_html()
        items = parse_latest_open_notices(html)[:max_results]
        print(f"=== {len(items)} currently-open bid notice(s) ===")
        for item in items:
            print(" -", item.get("procurement_ref"), "|", item.get("procuring_entity"), "|", item.get("deadline_date"))
        if items:
            notice_id = items[0]["notice_id"]
            status, dhtml = await client.fetch_notice_detail(notice_id)
            detail = parse_notice_detail(dhtml) if status == 200 else {"_detailError": f"HTTP {status}"}
            record = build_record("latest", "S1-bid-notices-live-tab", {**items[0], **detail})
            print("\nSample enriched record:")
            print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


async def run_archived(max_results: int, financial_year: str | None):
    client = EGPUgandaClient()
    try:
        body = await client.fetch_archived_bid_notices_page(0, max_results, financial_year)
        print(f"recordsTotal={body.get('recordsTotal')} (financialYear={financial_year!r})")
        rows = [clean_archived_record(r) for r in (body.get("data") or [])]
        for row in rows[:5]:
            print(" -", row.get("procurement_ref"), "|", row.get("procurement_name"), "|", row.get("submission_deadline"))
        if rows:
            notice_id = rows[0].get("notice_id")
            opening = None
            if notice_id:
                status, ohtml = await client.fetch_bid_opening_detail(notice_id)
                if status == 200 and ohtml:
                    opening = parse_bid_opening_detail(ohtml)
            record = build_record("archived", "S1-public-bids-archived-ajax", rows[0])
            if opening:
                record["bid_opening_result"] = opening
            print("\nSample record:")
            print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


async def run_detail(refs: list[str]):
    client = EGPUgandaClient()
    try:
        for ref in refs:
            notice_id = "".join(c for c in ref if c.isdigit()) or ref
            status, html = await client.fetch_notice_detail(notice_id)
            print(f"\n=== notice {notice_id} -> HTTP {status} ===")
            if status == 200:
                print(json.dumps(parse_notice_detail(html), ensure_ascii=False, indent=2))
            op_status, op_html = await client.fetch_bid_opening_detail(notice_id)
            if op_status == 200 and op_html:
                print("bid_opening_result:")
                print(json.dumps(parse_bid_opening_detail(op_html), ensure_ascii=False, indent=2))
            else:
                print(f"(no bid-opening record -- HTTP {op_status})")
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    mode = args[0]
    if mode == "latest":
        asyncio.run(run_latest(int(args[1]) if len(args) > 1 else 20))
    elif mode == "archived":
        asyncio.run(run_archived(int(args[1]) if len(args) > 1 else 5, args[2] if len(args) > 2 else None))
    elif mode == "detail":
        if len(args) < 2:
            print(__doc__)
            sys.exit(1)
        asyncio.run(run_detail(args[1:]))
    else:
        print(__doc__)
        sys.exit(1)
