"""Standalone local runner.

Usage:
    python test_local.py platform [slug]
    python test_local.py growth [slug]
    python test_local.py breakdown [slug] [dimension]
    python test_local.py migration [slug]
    python test_local.py stores [slug]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_platforms, run_reference


async def _no_proxy():
    return None


def show(records, limit=3, keys=None):
    for r in records[:limit]:
        print("   ", {k: r.get(k) for k in keys} if keys else json.dumps(r, ensure_ascii=False)[:500])
    print(f"-> {len(records)} record(s)\n")


async def collect(mode, platforms, dimensions=None, max_items=500):
    out = []

    async def push(records):
        out.extend(records)

    await run_platforms(mode, platforms, dimensions or [], max_items, 2, _no_proxy, push)
    return out


async def smoke():
    print("== reference: how many platform reports exist ==")
    ref = await run_reference(500, None)
    show(ref, 3, ["platform", "reportUrl"])
    assert len(ref) > 50, f"expected 100+ platform reports, got {len(ref)}"

    print("== platform: shopify headline ==")
    plat = await collect("platform", ["shopify"])
    show(plat, 1, ["platform", "liveStores", "quarterOverQuarterGrowthPct", "yearOverYearGrowthPct",
                   "latestQuarter", "quartersOfHistory", "reportUpdated"])
    assert plat and not plat[0].get("_error"), "platform mode returned no usable row"
    assert plat[0]["liveStores"] and plat[0]["liveStores"] > 1_000_000, "Shopify live store count looks wrong"
    assert plat[0]["quartersOfHistory"] > 20, "growth history did not parse"

    print("== platform: two more platforms (structure is not Shopify-specific) ==")
    multi = await collect("platform", ["woocommerce", "bigcommerce"])
    show(multi, 2, ["platform", "liveStores", "latestQuarter", "quartersOfHistory"])
    assert all(r.get("liveStores") for r in multi if not r.get("_error")), "a platform returned no store count"

    print("== growth: quarterly series ==")
    growth = await collect("growth", ["shopify"])
    show(growth, 3, ["platform", "quarter", "activeStores", "isPartialQuarter"])
    assert len(growth) > 20, "growth series too short"
    assert growth[0]["activeStores"] and growth[-1]["activeStores"], "growth rows missing numbers"
    assert any(r["isPartialQuarter"] for r in growth), "the in-progress quarter was not flagged"

    print("== breakdown: countries only ==")
    bd = await collect("breakdown", ["shopify"], ["country"])
    show(bd, 3, ["platform", "dimension", "label", "code", "stores"])
    assert bd and all(r["dimension"] == "country" for r in bd), "dimension filter leaked"
    assert any(r.get("code") for r in bd), "JS enrichment did not attach country codes"

    print("== breakdown: every dimension ==")
    allbd = await collect("breakdown", ["shopify"])
    dims = sorted({r["dimension"] for r in allbd})
    print("    dimensions:", dims)
    assert len(dims) >= 8, f"expected 8+ dimensions, got {dims}"

    print("== migration: switching in and out ==")
    mig = await collect("migration", ["shopify"])
    show(mig, 3, ["platform", "direction", "otherPlatform", "stores"])
    assert {r["direction"] for r in mig} == {"switched-in", "switched-out"}, "both directions should be present"

    print("== stores: top and new stores ==")
    st = await collect("stores", ["shopify"])
    show(st, 3, ["platform", "listType", "name", "domain", "rank", "created"])
    assert st and any(r.get("domain") for r in st), "store rows carry no domain"

    print("== unknown platform must fail loud ==")
    bad = await collect("platform", ["definitely-not-a-platform"])
    show(bad, 1, ["_input", "_error", "_errorDetail"])
    assert bad[0].get("_error") == "not_found", "unknown platform did not produce not_found"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    dim = sys.argv[3] if len(sys.argv) > 3 else None

    if mode == "all":
        await smoke()
    elif mode == "reference":
        show(await run_reference(500, None), 10, ["platform", "reportUrl"])
    else:
        show(await collect(mode, [arg or "shopify"], [dim] if dim else []), 8)


asyncio.run(main())
