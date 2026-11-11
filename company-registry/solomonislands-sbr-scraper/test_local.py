"""Standalone local runner -- exercises the search+detail flow without the
Apify platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --summary <query> [<query> ...]   # skip detail fetch
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import SBRClient
from src.extractor import NoResultsFound, build_detail_record, build_summary_record, extract_error


async def run(queries: list[str], fetch_details: bool):
    for query in queries:
        client = SBRClient()
        try:
            session = await client.start_search("")  # "any" register
            try:
                rows = await client.search(session, query)
            except NoResultsFound:
                print(json.dumps(extract_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row["label"], "|", row.get("entityTypeBadge"), "|", row.get("Entity Status"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")

            if not fetch_details:
                for row in rows[:3]:
                    record = build_summary_record(query, row)
                    print(json.dumps(record, ensure_ascii=False, indent=2))
                continue

            for row in rows[:2]:
                entity_url, detail_state, detail_html = await client.open_entity(session, query, row["nodeId"])
                detail = await client.fetch_entity_detail(detail_state, detail_html)
                record = build_detail_record(query, entity_url, detail)
                print(json.dumps(record, ensure_ascii=False, indent=2)[:3000], "...")
                print(f"-> _source={record['_source']} tabs={record.get('_tabs')}")
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    summary_only = False
    if args and args[0] == "--summary":
        summary_only = True
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, fetch_details=not summary_only))
