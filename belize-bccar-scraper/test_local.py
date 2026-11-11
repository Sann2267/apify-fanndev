"""Standalone local runner -- exercises the BCCAR search flow without the
Apify platform.

Usage:
    python test_local.py <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import BCCARClient
from src.extractor import build_record, extract_error
from src.main import _build_job


async def run(queries: list[str]):
    for q in queries:
        job = _build_job(q, entity_type=None)
        client = BCCARClient()
        try:
            items, total = await client.search_all(job["filters"], max_results=20)
            if not items:
                print(json.dumps(extract_error(job["label"], "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {job['label']!r} (filters={job['filters']}) -> {len(items)} of {total} match(es) ===")
            for entity in items[:5]:
                print(" -", entity.get("reg_number"), entity.get("name"), entity.get("business_entity_type_str"), entity.get("state"))
            if len(items) > 5:
                print(f"   ... {len(items) - 5} more")
            record = build_record(job["label"], items[0])
            print(json.dumps(record, ensure_ascii=False, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args))
