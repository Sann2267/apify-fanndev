"""Standalone local runner -- exercises the crawl flow without the Apify platform.

Usage:
    python test_local.py latest [maxItems]
    python test_local.py former [maxItems]
    python test_local.py awards [maxItems]
    python test_local.py detail-tender <id-or-url> [<id-or-url> ...]
    python test_local.py detail-award <id-or-url> [<id-or-url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_awards, run_detail_one, run_former, run_live


async def run(args: list[str]):
    mode = args[0] if args else "latest"

    if mode == "latest":
        max_items = int(args[1]) if len(args) > 1 else 5
        records = await run_live(None, max_items, True, 4)
    elif mode == "former":
        max_items = int(args[1]) if len(args) > 1 else 15
        records = await run_former(None, max_items, True, 4)
    elif mode == "awards":
        max_items = int(args[1]) if len(args) > 1 else 15
        records = await run_awards(None, max_items, True, 4)
    elif mode == "detail-tender":
        targets = args[1:] or ["46190"]
        records = await asyncio.gather(*(run_detail_one(t, "tender", None) for t in targets))
    elif mode == "detail-award":
        targets = args[1:] or ["8501"]
        records = await asyncio.gather(*(run_detail_one(t, "award", None) for t in targets))
    else:
        print(f"Unknown mode {mode!r}")
        return

    for record in records:
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2500])
    print(f"-> mode={mode!r} records={len(records)}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
