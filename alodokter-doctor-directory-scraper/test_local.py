"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py specialty <slug> [city] [maxItems]
    python test_local.py doctor <urlOrSlug> [...]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_doctor, run_reference, run_specialty


def show(records, limit=2):
    for r in records[:limit]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


async def smoke():
    print("== specialty dokter-anak (25 -> crosses page boundaries) ==")
    recs = await run_specialty("dokter-anak", None, 25, None)
    show(recs)
    cov = {k: sum(1 for r in recs if r.get(k) is not None)
           for k in ("name", "profileUrl", "hospital", "consultationPrice", "rating", "nextSchedule")}
    print("   field coverage:", cov, "\n")

    print("== dokter-gigi (the apostrophe/JSON-repair case) ==")
    gigi = await run_specialty("dokter-gigi", None, 10, None)
    print("   parsed:", len(gigi), "| names:", [r.get("name") for r in gigi][:4], "\n")

    print("== specialty + city ==")
    show(await run_specialty("dokter-anak", "jakarta", 3, None))

    print("== reference ==")
    ref = await run_reference(None)
    print("   specialties:", sum(1 for r in ref if r.get("recordType") == "SPECIALTY"),
          "| cities:", sum(1 for r in ref if r.get("recordType") == "CITY"), "\n")

    print("== doctor profile ==")
    url = next((r["profileUrl"] for r in recs if r.get("profileUrl")), None)
    print(json.dumps(await run_doctor(url, None), ensure_ascii=False, indent=2)[:1400], "...")

    print("\n== error paths ==")
    print(await run_specialty("dokter-tidak-ada", None, 3, None))
    print(await run_doctor("dr-tidak-ada-xyz", None))


async def main():
    args = sys.argv[1:] or ["all"]
    mode = args[0]
    if mode == "all":
        await smoke()
    elif mode == "specialty":
        city = args[2] if len(args) > 2 and not args[2].isdigit() else None
        n = int(args[-1]) if args[-1].isdigit() else 10
        show(await run_specialty(args[1], city, n, None), limit=3)
    elif mode == "doctor":
        for raw in args[1:]:
            print(json.dumps(await run_doctor(raw, None), ensure_ascii=False, indent=2)[:1600])
    elif mode == "reference":
        show(await run_reference(None), limit=5)
    else:
        print(__doc__)


asyncio.run(main())
