"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py avis [--max N]
    python test_local.py dossiers [--year YYYY] [--max N]
    python test_local.py contrats [--year YYYY] [--max N]
"""

import asyncio
import json
import sys
from datetime import datetime, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_avis, run_contrats, run_dossiers


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    list_type = args[0]
    max_results = 15
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])
    year = str(datetime.now(timezone.utc).year)
    if "--year" in args:
        year = args[args.index("--year") + 1]

    if list_type == "avis":
        records = await run_avis(max_results, _null_proxy)
    elif list_type == "dossiers":
        records = await run_dossiers(year, max_results, _null_proxy)
    elif list_type == "contrats":
        records = await run_contrats(year, max_results, _null_proxy)
    else:
        print(__doc__)
        sys.exit(1)

    print(f"=== listType={list_type} year={year} -> {len(records)} record(s) ===")
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    if len(records) > 5:
        print(f"... and {len(records) - 5} more")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
