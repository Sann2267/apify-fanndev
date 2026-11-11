"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py post <url> [<url> ...]
    python test_local.py archive <url> [sort] [maxItems]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_archive, run_post


async def run_p(urls: list[str]):
    for u in urls:
        record = await run_post(u, None)
        preview = dict(record)
        if "markdown" in preview:
            preview["markdown"] = preview["markdown"][:600] + "...<truncated>"
        if "body_html" in preview:
            preview["body_html"] = f"<{len(preview['body_html'] or '')} chars>"
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_a(url: str, sort: str, max_items: int):
    records = await run_archive(url, sort, max_items, 4, None)
    for r in records:
        preview = dict(r)
        if "markdown" in preview:
            preview["markdown"] = preview["markdown"][:300] + "...<truncated>"
        if "body_html" in preview:
            preview["body_html"] = f"<{len(preview['body_html'] or '')} chars>"
        print(json.dumps(preview, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} record(s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "post"
    if mode == "post":
        urls = sys.argv[2:] or ["https://noahpinion.substack.com/p/the-death-of-market-street"]
        asyncio.run(run_p(urls))
    elif mode == "archive":
        url = sys.argv[2] if len(sys.argv) > 2 else "noahpinion.substack.com"
        sort = sys.argv[3] if len(sys.argv) > 3 else "new"
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        asyncio.run(run_a(url, sort, max_items))
    else:
        print("Usage: python test_local.py [post <url>... | archive <url> [sort] [maxItems]]")
        sys.exit(1)
