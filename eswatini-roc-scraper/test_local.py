"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import EswatiniROCClient
from src.extractor import NoResultsFound, build_record, extract_error


async def run(queries: list[str]):
    for query in queries:
        client = EswatiniROCClient()
        try:
            try:
                rows = await client.search(query)
            except NoResultsFound:
                print(json.dumps(extract_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(rows)} match(es) ===")
            for row in rows[:5]:
                print(" -", row["companyName"], "|", row["companyStatus"], "|", row["dateRegistered"])
            if len(rows) > 5:
                print(f"   ... {len(rows) - 5} more")
            for row in rows[:3]:
                record = build_record(query, row)
                print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args))
