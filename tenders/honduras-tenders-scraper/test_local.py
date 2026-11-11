"""Standalone local runner -- exercises the search/detail flow without the
Apify platform.

Usage:
    python test_local.py list [maxResults] [etapa]
    python test_local.py detail <url>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import HonduComprasClient
from src.constants import ETAPA_VALUES
from src.extractor import UnexpectedShape, build_detail_record, build_list_record, parse_detail


async def run_list(max_results: int, etapa_key: str):
    etapa = ETAPA_VALUES.get(etapa_key, "0")
    client = HonduComprasClient()
    try:
        rows, filters_used = await client.search_list(etapa=etapa, max_results=max_results)
    finally:
        await client.close()

    print(f"\n=== list etapa={etapa_key!r} -> {len(rows)} tender(s) ===")
    for row in rows[:5]:
        print(" -", row["expediente"], "|", row["entidad"], "|", row["etapa"], "|", row["fechaInicio"], "-", row["fechaCierre"])
    if len(rows) > 5:
        print(f"   ... {len(rows) - 5} more")

    for row in rows[:2]:
        record = build_list_record(row, filters_used)
        print(json.dumps(record, ensure_ascii=False, indent=2))


async def run_detail(url: str):
    client = HonduComprasClient()
    try:
        html = await client.fetch_detail(url)
        try:
            detail = parse_detail(html, url)
        except UnexpectedShape as e:
            print(f"UnexpectedShape: {e}")
            return
        record = build_detail_record(url, detail)
        print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        max_results = int(args[1]) if len(args) > 1 else 10
        etapa_key = args[2] if len(args) > 2 else "todas"
        asyncio.run(run_list(max_results, etapa_key))
    elif args[0] == "detail":
        if len(args) < 2:
            print("Usage: python test_local.py detail <url>")
            sys.exit(1)
        asyncio.run(run_detail(args[1]))
    else:
        print(__doc__)
        sys.exit(1)
