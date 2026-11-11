"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py entity <query> [<query> ...]
    python test_local.py individual <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import MBRSClient
from src.extractor import (
    build_record,
    extract_error,
    parse_entity_page,
    parse_individual_page,
    parse_owner_detail,
)
from src.main import MAX_PAGES_PER_QUERY


async def run(search_type: str, queries: list[str]):
    parse_page = parse_entity_page if search_type == "entity" else parse_individual_page
    for query in queries:
        client = MBRSClient()
        try:
            items = []
            page = 1
            while len(items) < 20 and page <= MAX_PAGES_PER_QUERY:
                html = await client.fetch_search_page(search_type, query, page)
                page_items = parse_page(html)
                if not page_items:
                    break
                items.extend(page_items)
                page += 1
            items = items[:20]

            if not items:
                print(json.dumps(extract_error(query, search_type, "not_found"), ensure_ascii=False))
                continue

            print(f"\n=== {query!r} ({search_type}) -> {len(items)} match(es) ===")
            for item in items[:5]:
                print(" -", item.get("name"), item.get("registrationNumber"), item.get("status"))
            if len(items) > 5:
                print(f"   ... {len(items) - 5} more")

            if search_type == "individual" and items[0].get("ownerId"):
                detail_html = await client.fetch_owner_detail(items[0]["ownerId"])
                detail = parse_owner_detail(detail_html)
                items[0]["ownerIdType"] = detail["ownerIdType"]
                items[0]["businesses"] = detail["businesses"]

            record = build_record(query, search_type, items[0])
            print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("entity", "individual"):
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args[0], args[1:]))
