"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]
    python test_local.py --history <query> [<query> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import BahamasRGDClient, TooBroadError
from src.extractor import build_record, extract_error


async def run(queries: list[str], include_history: bool):
    for query in queries:
        client = BahamasRGDClient()
        try:
            items = await client.search(query, include_history)
            if not items:
                print(json.dumps(extract_error(query, "not_found"), ensure_ascii=False))
                continue
            print(f"\n=== {query!r} -> {len(items)} match(es) (includeHistory={include_history}) ===")
            for item in items:
                if include_history:
                    print(" -", item.get("name"), "->", item.get("entity", {}).get("entityName"))
                else:
                    print(" -", item.get("entityName"), item.get("entityId"))
            record = build_record(query, items[0], include_history)
            print(json.dumps(record, ensure_ascii=False, indent=2))
        except TooBroadError as e:
            print(json.dumps(extract_error(query, "result_set_too_broad", repr(e)), ensure_ascii=False))
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    history = False
    if args and args[0] == "--history":
        history = True
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, history))
