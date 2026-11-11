"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py category <slug> [city] [maxItems]
    python test_local.py company <urlOrId> [...]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_category, run_company, run_reference


def show(records, limit=2):
    for r in records[:limit]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"-> {len(records)} record(s)\n")


async def smoke():
    print("== category restaurants (25 -> crosses a page boundary) ==")
    recs = await run_category("restaurants", None, 25, None)
    show(recs)
    cov = {k: sum(1 for r in recs if r.get(k) is not None)
           for k in ("name", "profileUrl", "address", "city", "phone", "rating", "establishedYear")}
    print("   field coverage of", len(recs), "cards:", cov, "\n")

    print("== category lawyers, city:Jakarta ==")
    show(await run_category("lawyers", "Jakarta", 3, None))

    print("== reference ==")
    ref = await run_reference(None)
    print("   categories:", sum(1 for r in ref if r.get("recordType") == "CATEGORY"),
          "| cities:", sum(1 for r in ref if r.get("recordType") == "CITY"), "\n")

    print("== company detail ==")
    url = next((r["profileUrl"] for r in recs if r.get("profileUrl")), None)
    rec = await run_company(url, None)
    print(json.dumps(rec, ensure_ascii=False, indent=2)[:1500], "...")

    print("\n== error path ==")
    print(await run_company("not-a-company", None))


async def main():
    args = sys.argv[1:] or ["all"]
    mode = args[0]
    if mode == "all":
        await smoke()
    elif mode == "category":
        city = args[2] if len(args) > 2 and not args[2].isdigit() else None
        n = int(args[-1]) if args[-1].isdigit() else 5
        show(await run_category(args[1], city, n, None), limit=3)
    elif mode == "company":
        for raw in args[1:]:
            print(json.dumps(await run_company(raw, None), ensure_ascii=False, indent=2)[:1800])
    elif mode == "reference":
        show(await run_reference(None), limit=5)
    else:
        print(__doc__)


asyncio.run(main())
