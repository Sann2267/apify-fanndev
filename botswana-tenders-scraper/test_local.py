"""Standalone local runner -- exercises the finance/health flows without the
Apify platform.

Usage:
    python test_local.py finance
    python test_local.py health
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import BotswanaTendersClient
from src.extractor import build_record, parse_finance_rss, parse_health_tenders


async def run_finance():
    client = BotswanaTendersClient()
    try:
        xml_text = await client.fetch_finance_rss()
        records = parse_finance_rss(xml_text)
        print(f"=== Ministry of Finance: {len(records)} procurement notice(s) ===")
        for r in records:
            print(" -", r["pub_date"], "|", r["title"])
        if records:
            print("\nSample record:")
            print(json.dumps(build_record("finance", "S1-mof-procurement-rss", records[0]), ensure_ascii=False, indent=2))
    finally:
        await client.close()


async def run_health():
    client = BotswanaTendersClient()
    try:
        html_text = await client.fetch_health_tenders_page()
        records = parse_health_tenders(html_text)
        print(f"=== Ministry of Health: {len(records)} tender(s) ===")
        for r in records:
            print(" -", r["closing_date"], "|", r["title"])
        if records:
            print("\nSample record:")
            print(json.dumps(build_record("health", "S2-moh-tenders-table", records[0]), ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args else "all"
    if mode not in ("finance", "health", "all"):
        print(__doc__)
        sys.exit(1)
    if mode in ("finance", "all"):
        asyncio.run(run_finance())
    if mode in ("health", "all"):
        print()
        asyncio.run(run_health())
