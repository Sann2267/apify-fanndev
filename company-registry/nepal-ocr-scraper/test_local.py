"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --by registrationNumber <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import OCRClient
from src.extractor import NoResultsFound, build_error, build_record, build_request_body, extract_records


async def run(queries: list[str], search_by: str):
    for query in queries:
        client = OCRClient()
        try:
            body = build_request_body(query, search_by)
            payload = await client.search_company(body)
            try:
                rows = extract_records(payload)
            except NoResultsFound:
                print(json.dumps(build_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} ({body}) -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row.get("companyNameEnglish"), "|", row.get("companyRegistrationNumberEn"))
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:2]:
                record = build_record(query, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    search_by = "auto"
    if args and args[0] == "--by":
        search_by = args[1]
        args = args[2:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, search_by))
