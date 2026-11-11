"""Standalone local runner.

Usage:
    python test_local.py list [maxItems]
    python test_local.py property [id]
    python test_local.py range [startId] [count]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_list, run_properties, run_reference


async def _no_proxy():
    return None


def show(records, limit=3, keys=None):
    for r in records[:limit]:
        print("   ", {k: r.get(k) for k in keys} if keys else json.dumps(r, ensure_ascii=False)[:500])
    print(f"-> {len(records)} record(s)\n")


async def collect_list(max_items=24, perpage=12, details=False):
    out = []

    async def push(records):
        out.extend(records)

    await run_list(max_items, perpage, 1, details, 3, _no_proxy, push)
    return out


async def collect_props(ids, max_items=50):
    out = []

    async def push(records):
        out.extend(records)

    await run_properties(ids, max_items, 3, _no_proxy, push)
    return out


LIST_KEYS = ["propertyId", "districtCourt", "enforcementAgent", "biddingStart", "biddingEnd",
             "announcementAt", "locality", "listPage", "totalPages"]
DET_KEYS = ["propertyId", "locality", "propertyType", "area", "areaUnit", "startingPriceEur",
            "startingPriceBgn", "biddingEnd", "agentPhone", "agentEmail"]


async def smoke():
    print("== reference ==")
    ref = await run_reference(None)
    show(ref, 1, ["isAvailable", "detail", "sample"])
    assert ref[0]["isAvailable"], "the portal is not answering"
    assert ref[0]["sample"]["totalPages"], "pagination was not detected"

    print("== list: two pages ==")
    rows = await collect_list(24, 12, False)
    show(rows, 2, LIST_KEYS)
    assert len(rows) == 24, f"expected 24 rows across two pages, got {len(rows)}"
    assert len({r["propertyId"] for r in rows}) == 24, "pages returned duplicate properties"
    assert len({r["listPage"] for r in rows}) == 2, "paging did not advance (check perpage/p params)"
    assert rows[0]["districtCourt"] and rows[0]["enforcementAgent"], "card fields missing"
    assert rows[0]["biddingEnd"] and rows[0]["biddingEnd"][4] == "-", "bidding period not parsed to ISO"

    print("== property: one detail page ==")
    target = rows[0]["propertyId"]
    det = await collect_props([target])
    show(det, 1, DET_KEYS)
    rec = det[0]
    assert not rec.get("_error"), f"detail failed: {rec.get('_errorDetail')}"
    assert rec["description"], "description missing"
    assert rec["startingPriceEur"] or rec["startingPriceBgn"], "no starting price parsed"
    # The filter sidebar publishes round bounds (10 000 / 50 000 lv). A price
    # equal to one of those is the sidebar leaking into the record again.
    assert rec["startingPriceBgn"] not in (10000, 50000, 100000, 250000), (
        f"price {rec['startingPriceBgn']} looks like a filter bound, not the sale price"
    )
    assert rec["agentPhone"] or rec["agentMobile"], "agent contact missing"
    assert rec["fields"], "raw published fields missing"

    print("== property: accepts a full URL ==")
    by_url = await collect_props([f"https://sales.bcpea.org/properties/{target}"])
    show(by_url, 1, ["propertyId", "locality"])
    assert by_url[0]["propertyId"] == target, "URL input was not normalised"

    print("== list with details ==")
    enriched = await collect_list(4, 12, True)
    show(enriched, 2, DET_KEYS + ["detailFetched"])
    assert all(r.get("detailFetched") for r in enriched if not r.get("_detailError")), "details were not fetched"

    print("== unknown id fails loud ==")
    bad = await collect_props(["999999999"])
    show(bad, 1, ["_input", "_error", "_errorDetail"])
    assert bad[0].get("_error"), "an impossible id produced no error row"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if mode == "all":
        await smoke()
    elif mode == "list":
        show(await collect_list(int(arg or 12), 12, False), 5, LIST_KEYS)
    elif mode == "property":
        show(await collect_props([arg or "92433"]), 1)
    elif mode == "range":
        start = int(arg or 92433)
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        show(await collect_props([str(start + i) for i in range(count)]), count, DET_KEYS)
    elif mode == "reference":
        show(await run_reference(None), 1)
    else:
        print(__doc__)


asyncio.run(main())
