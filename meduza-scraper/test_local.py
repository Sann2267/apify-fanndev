"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py latest [limit] [en|ru]
    python test_local.py article <url> [<url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import MeduzaClient
from src.constants import RSS_URL_EN, RSS_URL_RU
from src.extractor import extract_article, extract_error, extract_rss_items


async def run_latest(limit: int, language: str):
    feed_url = RSS_URL_RU if language == "ru" else RSS_URL_EN
    client = MeduzaClient()
    try:
        r = await client.get(feed_url)
        assert r.status_code == 200, f"RSS feed returned {r.status_code}"
        items = extract_rss_items(r.text)[:limit]
        for item in items:
            print(json.dumps(item, ensure_ascii=False, indent=2)[:1200], "...")
        print(f"\n-> {len(items)} headline(s) from {feed_url}")
    finally:
        await client.close()


async def run_article(urls: list[str]):
    client = MeduzaClient()
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
            print(f"-> _source={record.get('_source')} _error={record.get('_error')} _warning={record.get('_warning')}")
    finally:
        await client.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "latest"
    if mode == "latest":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        language = sys.argv[3] if len(sys.argv) > 3 else "en"
        asyncio.run(run_latest(limit, language))
    elif mode == "article":
        urls = sys.argv[2:]
        if not urls:
            print("Usage: python test_local.py article <url> [<url> ...]")
            sys.exit(1)
        asyncio.run(run_article(urls))
    else:
        print("Usage: python test_local.py [latest [limit] [en|ru] | article <url> ...]")
        sys.exit(1)
