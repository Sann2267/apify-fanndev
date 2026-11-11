"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py directory [city] [maxItems]
    python test_local.py area <practiceArea> [maxItems]
    python test_local.py profile <urlOrSlug> [...]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_directory, run_profile, run_reference


def show(records, limit=2):
    for r in records[:limit]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


async def smoke():
    print("== directory (all India, 25 = crosses a page boundary) ==")
    recs = await run_directory(None, None, 25, None)
    show(recs)
    filled = {k: sum(1 for r in recs if r.get(k) is not None) for k in
              ("name", "profileUrl", "rating", "ratingCount", "experienceYears", "locality")}
    print("   field coverage:", filled, "\n")

    print("== directory (city=delhi) ==")
    show(await run_directory("delhi", None, 3, None))

    print("== directory (practiceArea=divorce) ==")
    show(await run_directory(None, "divorce", 3, None))

    print("== reference ==")
    ref = await run_reference(None)
    print("   cities:", sum(1 for r in ref if r.get("recordType") == "CITY"),
          "| practice areas:", sum(1 for r in ref if r.get("recordType") == "PRACTICE_AREA"), "\n")

    print("== profile ==")
    rec = await run_profile("https://lawrato.com/advocate-sunil-kumar-bakshi", None)
    print(json.dumps(rec, ensure_ascii=False, indent=2)[:1600], "...")

    print("\n== error path (bogus slug) ==")
    print(await run_profile("advocate-this-does-not-exist-xyz", None))


async def main():
    args = sys.argv[1:] or ["all"]
    mode = args[0]
    if mode == "all":
        await smoke()
    elif mode == "directory":
        city = args[1] if len(args) > 1 else None
        n = int(args[2]) if len(args) > 2 else 5
        show(await run_directory(city, None, n, None), limit=3)
    elif mode == "area":
        n = int(args[2]) if len(args) > 2 else 5
        show(await run_directory(None, args[1], n, None), limit=3)
    elif mode == "profile":
        for raw in args[1:]:
            print(json.dumps(await run_profile(raw, None), ensure_ascii=False, indent=2)[:1800])
    elif mode == "reference":
        show(await run_reference(None), limit=4)
    else:
        print(__doc__)


asyncio.run(main())
