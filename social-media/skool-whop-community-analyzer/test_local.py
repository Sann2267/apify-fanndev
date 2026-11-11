"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py skool <url> [<url> ...]
    python test_local.py whop <url> [<url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_skool, run_whop


async def run(mode: str, urls: list[str]):
    fn = run_skool if mode == "skool" else run_whop
    for u in urls:
        record = await fn(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2000], "...")
        print(
            f"-> _source={record.get('_source')} _error={record.get('_error')} "
            f"memberCount={record.get('memberCount')} "
            f"estimatedMonthlyRevenue={record.get('estimatedMonthlyRevenue')}"
        )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "skool"
    if mode not in ("skool", "whop"):
        print("Usage: python test_local.py [skool|whop] <url> [<url> ...]")
        sys.exit(1)
    urls = sys.argv[2:] or (["skool-100"] if mode == "skool" else ["kaizen"])
    asyncio.run(run(mode, urls))
