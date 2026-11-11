"""Standalone local runner -- exercises all 5 modes without the Apify platform.

Usage:
    python test_local.py catalog [search] [maxItems]
    python test_local.py kpknl <office> [maxItems]
    python test_local.py detail <lotIdOrUrl> [...]
    python test_local.py feed [hot|ending-soon|live] [maxItems]
    python test_local.py reference
    python test_local.py all           # smoke-test every mode
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_catalog, run_detail, run_feed, run_kpknl, run_reference


def show(records, limit=2):
    for r in records[:limit]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


async def smoke():
    print("== catalog (search=toyota) ==")
    cat = await run_catalog("toyota", None, False, 5, None)
    show(cat)

    print("== catalog (categories=[Rumah]) ==")
    show(await run_catalog(None, ["Rumah"], False, 3, None))

    print("== kpknl (Denpasar) ==")
    show(await run_kpknl("Denpasar", None, None, 3, None))

    print("== feed (ending-soon) ==")
    show(await run_feed("ending-soon", 3, None))

    print("== reference ==")
    ref = await run_reference(None)
    cats = [r for r in ref if r.get("recordType") == "CATEGORY"]
    offices = [r for r in ref if r.get("recordType") == "KPKNL_OFFICE"]
    print(f"-> {len(cats)} categories, {len(offices)} KPKNL offices\n")

    print("== detail (first catalogue lot) ==")
    lot_id = next((r.get("lotLelangId") for r in cat if r.get("lotLelangId")), None)
    if lot_id:
        rec = await run_detail(lot_id, None)
        print(json.dumps(rec, ensure_ascii=False, indent=2)[:1200], "...")
        print(f"-> _error={rec.get('_error')} barangs={len((rec.get('content') or {}).get('barangs') or [])}")

    print("\n== error path (bogus id) ==")
    print(await run_detail("not-a-uuid", None))


async def main():
    args = sys.argv[1:] or ["all"]
    mode = args[0]

    if mode == "all":
        await smoke()
    elif mode == "catalog":
        search = args[1] if len(args) > 1 else None
        n = int(args[2]) if len(args) > 2 else 5
        show(await run_catalog(search, None, False, n, None), limit=3)
    elif mode == "kpknl":
        n = int(args[2]) if len(args) > 2 else 5
        show(await run_kpknl(args[1], None, None, n, None), limit=3)
    elif mode == "detail":
        for raw in args[1:]:
            rec = await run_detail(raw, None)
            print(json.dumps(rec, ensure_ascii=False, indent=2)[:1500], "...")
    elif mode == "feed":
        feed = args[1] if len(args) > 1 else "hot"
        n = int(args[2]) if len(args) > 2 else 5
        show(await run_feed(feed, n, None), limit=3)
    elif mode == "reference":
        show(await run_reference(None), limit=4)
    else:
        print(__doc__)


asyncio.run(main())
