"""Standalone local runner -- exercises the search(+detail) flow without the
Apify platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --type directors <surname> [<surname> ...]
    python test_local.py --summary <query> [<query> ...]   # skip detail fetch
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import CIPOClient
from src.extractor import InvalidQuery, NoResultsFound, UpstreamError, build_record, extract_error


async def run(queries: list[str], search_type: str, fetch_details: bool):
    for query in queries:
        client = CIPOClient()
        try:
            try:
                rows = await client.search(query, search_type)
            except InvalidQuery as e:
                print(json.dumps(extract_error(query, search_type, "invalid_query", str(e)), ensure_ascii=False))
                continue
            except NoResultsFound:
                print(json.dumps(extract_error(query, search_type, "not_found"), ensure_ascii=False))
                continue
            except UpstreamError as e:
                print(json.dumps(extract_error(query, search_type, "upstream_error", str(e)), ensure_ascii=False))
                continue

            print(f"\n=== {query!r} ({search_type}) -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row.get("EntityName"), row.get("EntityNumber"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")

            for row in rows[:2]:
                if fetch_details:
                    entity_id = row.get("EntityID")
                    detail = await client.entity_info(entity_id) if entity_id else {}
                    record = build_record(query, search_type, row, detail)
                else:
                    record = build_record(query, search_type, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    search_type = "entities"
    if args and args[0] == "--type":
        search_type = args[1]
        args = args[2:]
    summary_only = False
    if args and args[0] == "--summary":
        summary_only = True
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, search_type, fetch_details=not summary_only))
