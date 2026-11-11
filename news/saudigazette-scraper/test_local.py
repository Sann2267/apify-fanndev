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

from src.client import SaudiGazetteClient
from src.constants import NEWS_SITEMAP_URL
from src.extractor import extract_article, extract_error, extract_sitemap_items


async def run_latest(limit: int):
    client = SaudiGazetteClient()
    try:
        r = await client.get(NEWS_SITEMAP_URL)
        assert r.status_code == 200, f"News sitemap returned {r.status_code}"
        items = extract_sitemap_items(r.content)[:limit]
        for item in items:
            print(json.dumps(item, ensure_ascii=False, indent=2)[:1200], "...")
        print(f"\n-> {len(items)} headline(s)")
    finally:
        await client.close()


async def run_article(urls: list[str]):
    client = SaudiGazetteClient()
    try:
        for url in urls:
            r = await client.get(url)
            if r.status_code == 404:
                record = extract_error(url, "not_found")
            elif r.status_code != 200:
                record = extract_error(url, f"http_{r.status_code}")
            else:
                record = extract_article(r.text, url)
            print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
            print(f"-> _source={record.get('_source')} _error={record.get('_error')}")
    finally:
        await client.close()


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
