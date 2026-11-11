"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py latest [limit]
    python test_local.py article <url> [<url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import fetch_latest, process_article


async def run_latest(limit: int):
    items = await fetch_latest(limit, proxy_url=None)
    for item in items:
        print(json.dumps(item, ensure_ascii=False, indent=2)[:1200], "...")
    print(f"\n-> {len(items)} headline(s)")


async def run_article(urls: list[str]):
    for url in urls:
        record = await process_article(url, proxy_url=None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "latest"
    if mode == "latest":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        asyncio.run(run_latest(limit))
    elif mode == "article":
        urls = sys.argv[2:]
        if not urls:
            print("Usage: python test_local.py article <url> [<url> ...]")
            sys.exit(1)
        asyncio.run(run_article(urls))
    else:
        print("Usage: python test_local.py [latest [limit] | article <url> ...]")
        sys.exit(1)
