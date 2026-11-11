"""Standalone local runner.

Usage:
    python test_local.py <query> [targetDomain]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_bing_serp


async def run(query: str, target: str | None):
    record = await run_bing_serp(query, target, None)
    print(json.dumps(record, ensure_ascii=False, indent=2)[:2000], "...")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "which crm software is best for small business"
    target = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(run(query, target))
