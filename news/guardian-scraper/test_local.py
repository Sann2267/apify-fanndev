import asyncio
import json
import sys

from src.client import GuardianClient
from src.extractor import extract_jsonld_article, extract_error, extract_rss_items


async def run_latest(section: str, limit: int):
    client = GuardianClient()
    try:
        r = await client.get('https://www.theguardian.com/world/rss')
        assert r.status_code == 200, f"RSS feed returned {r.status_code}"
        items = extract_rss_items(r.content, section)[:limit]
        for item in items:
            print(json.dumps(item, ensure_ascii=False, indent=2))
        print(f"\n-> {len(items)} headline(s) from '{section}'")
    finally:
        await client.close()


async def run_article(urls: list[str]):
    client = GuardianClient()
    try:
        for url in urls:
            r = await client.get(url)
            if r.status_code == 404:
                record = extract_error(url, 'not_found')
            elif r.status_code != 200:
                record = extract_error(url, f'http_{r.status_code}')
            else:
                try:
                    record = extract_jsonld_article(r.text, url)
                except ValueError as exc:
                    record = extract_error(url, 'unexpected_shape', repr(exc))
            print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], '...')
            print(f"-> _source={record.get('_source')} _error={record.get('_error')}")
    finally:
        await client.close()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'latest'
    if mode == 'latest':
        section = sys.argv[2] if len(sys.argv) > 2 else 'world'
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        asyncio.run(run_latest(section, limit))
    elif mode == 'article':
        urls = sys.argv[2:]
        if not urls:
            print('Usage: python test_local.py article <url> [<url> ...]')
            sys.exit(1)
        asyncio.run(run_article(urls))
    else:
        print('Usage: python test_local.py [latest [section] [limit] | article <url> ...]')
        sys.exit(1)
