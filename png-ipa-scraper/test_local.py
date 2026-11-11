"""Standalone local runner -- exercises search + profile lookup without the
Apify platform.

Usage:
    python test_local.py search <term> [<term> ...]
    python test_local.py profile <corpId> [<corpId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import process_corp_id, process_search_term


async def run_search(terms: list[str]):
    for term in terms:
        records = await process_search_term(
            term, max_results=5, fetch_profiles=True, entity_type_id=None, proxy_url=None
        )
        print(f"\n=== {term} -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:1500], "...")
            print(f"-> _source={r.get('_source')} _error={r.get('_error')}")


async def run_profile(corp_ids: list[str]):
    for corp_id in corp_ids:
        record = await process_corp_id(corp_id, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2000], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    args = sys.argv[2:]
    if mode == "search":
        if not args:
            print("Usage: python test_local.py search <term> [<term> ...]")
            sys.exit(1)
        asyncio.run(run_search(args))
    elif mode == "profile":
        if not args:
            print("Usage: python test_local.py profile <corpId> [<corpId> ...]")
            sys.exit(1)
        asyncio.run(run_profile(args))
    else:
        print("Usage: python test_local.py [search <term> ... | profile <corpId> ...]")
        sys.exit(1)
