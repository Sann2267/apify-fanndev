"""Local smoke test -- runs the actor's real code paths without the Apify platform.

Usage:
    python test_local.py              # every mode, small caps
    python test_local.py listings     # one mode
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.client import SteamClient
from src.main import run_mode


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")

    def error(self, message):
        print(f"  [err ] {message}")


LOG = Log()

CASES = {
    "search": [
        ("CS2 popular", {"appId": "cs2", "maxItems": 150}),
        ("cases only, cheapest first", {"appId": 730, "searchFilters": {"Type": ["CSGO_Type_WeaponCase"]}, "sortBy": "priceAsc", "maxItems": 5}),
        ("knives $1000-2000", {"searchQuery": "knife", "minPrice": 1000, "maxPrice": 2000, "maxItems": 5}),
        ("dota2", {"appId": "dota2", "maxItems": 3}),
    ],
    "itemOverview": [
        ("explicit + bad", {"items": ["AK-47 | Redline (Field-Tested)", "Dreams & Nightmares Case", "Not A Real Item"], "orderBookDepth": 3}),
    ],
    "priceHistory": [
        ("perItem 30d", {"items": ["https://steamcommunity.com/market/listings/730/AWP%20%7C%20Asiimov%20(Field-Tested)"], "historyDays": 30}),
        ("perPoint 3d", {"items": ["Mann Co. Supply Crate Key"], "appId": "tf2", "historyDays": 3, "historyOutput": "perPoint"}),
        ("from search", {"appId": 730, "searchFilters": {"Type": ["CSGO_Type_WeaponCase"]}, "maxItems": 3, "historyDays": 7}),
    ],
    "orderBook": [
        ("group URL expands", {"items": ["https://steamcommunity.com/market/listings/730/G1807209A023004"], "orderBookDepth": 3}),
    ],
    "listings": [
        ("floatAsc max 0.16", {"items": ["AK-47 | Redline (Field-Tested)"], "listingSort": "floatAsc", "maxFloat": 0.16, "maxListingsPerItem": 30}),
        ("group, 25 rows", {"items": ["https://steamcommunity.com/market/listings/730/G1807209A023004"], "maxListingsPerItem": 25}),
        ("commodity + bad", {"items": ["Dreams & Nightmares Case", "Not A Real Item"], "maxListingsPerItem": 5}),
    ],
    "recentSales": [
        ("2 polls", {"recentSalesPolls": 2, "recentSalesIntervalSecs": 5}),
    ],
}

SHOW = {
    "ITEM": ["marketHashName", "sellListings", "minSellPriceText", "currency", "type"],
    "ITEM_OVERVIEW": ["marketHashName", "currency", "highestBuyOrder", "lowestSellOrder", "spreadPct", "avgPrice7d", "volume7d", "allTimeHigh", "historyPoints"],
    "PRICE_HISTORY": ["marketHashName", "currency", "historyPoints", "lastMedianPrice", "avgPrice24h", "volume30d", "change7dVs30dPct"],
    "PRICE_POINT": ["marketHashName", "time", "medianPrice", "volume", "currency"],
    "ORDER_BOOK": ["marketHashName", "currency", "highestBuyOrder", "lowestSellOrder", "buyOrderQuantity", "buyPriceLevels", "buyOrders"],
    "LISTING": ["marketHashName", "listingRank", "price", "currency", "floatValue", "paintSeed", "stickers"],
    "SALE": ["appName", "marketHashName", "soldAt", "soldPriceText"],
    "ERROR": ["_input", "_error", "_errorDetail"],
}


async def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    client = SteamClient(max_concurrency=4, log=LOG)
    try:
        for mode, cases in CASES.items():
            if which not in ("all", mode):
                continue
            for title, inp in cases:
                records: list[dict] = []

                async def emit(batch):
                    records.extend(batch)

                print(f"\n=== {mode} / {title} ===")
                await run_mode(client, {"mode": mode, **inp}, mode, emit, LOG)
                kinds: dict = {}
                for r in records:
                    kinds[r["recordType"]] = kinds.get(r["recordType"], 0) + 1
                print(f"  -> {len(records)} record(s) {kinds}")
                shown: dict = {}
                for r in records:
                    rt = r["recordType"]
                    if shown.get(rt, 0) >= 3:
                        continue
                    shown[rt] = shown.get(rt, 0) + 1
                    line = {f: r.get(f) for f in SHOW.get(rt, [])}
                    print("    " + json.dumps(line, ensure_ascii=False, default=str)[:400])
                for r in records:
                    assert r.get("_input") and r.get("_source") and r.get("_scrapedAt") and r.get("recordType"), r
    finally:
        await client.close()
        print(f"\nHTTP requests made: {client.requests_made}")


if __name__ == "__main__":
    asyncio.run(main())
