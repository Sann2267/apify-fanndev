"""Local smoke test -- exercises all seven modes against the live site.

Runs the actor's real client/mode code with a stub emitter, so it proves the
same path the Actor takes without needing the Apify platform.

    python test_local.py            # all modes
    python test_local.py search     # one mode
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from src.client import MobileDeClient
from src.modes import (
    Budget,
    run_dealer_contact,
    run_dealer_inventory,
    run_detail,
    run_market_count,
    run_reference_data,
    run_search,
    run_similar_ads,
)
from src.parsers import build_search_path, flatten_items

logging.basicConfig(
    level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger("test")


class Collector:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def __call__(self, row: dict) -> None:
        self.rows.append(row)

    def by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r["item_type"]] = out.get(r["item_type"], 0) + 1
        return out


def show(name: str, c: Collector, sample_type: str | None = None) -> bool:
    types = c.by_type()
    errors = [r for r in c.rows if r["item_type"] == "error"]
    ok = bool(c.rows) and not errors
    print(f"\n--- {name} ---")
    print(f"  rows: {len(c.rows)}  types: {types}")
    for e in errors[:3]:
        print(f"  ERROR ROW: {e['data']['_error']}: {e['data']['_errorDetail'][:160]}")
    if sample_type:
        sample = next((r for r in c.rows if r["item_type"] == sample_type), None)
        if sample:
            keys = list(sample["data"].keys())
            print(f"  sample {sample_type} id={sample['id']} keys[{len(keys)}]={keys[:14]}")
    print(f"  => {'PASS' if ok else 'FAIL'}")
    return ok


async def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    client = MobileDeClient(delay=0.3)
    results: dict[str, bool] = {}
    ad_id: str | None = None
    seller_id: str | None = None

    try:
        # 1. search -- BMW 1er, narrow enough to finish fast
        if only in (None, "search"):
            c = Collector()
            path = build_search_path(
                {"vc": "Car", "ms": "3500;;21;", "p": ":25000", "sb": "doc", "od": "down"}
            )
            log.info("search path: %s", path)
            await run_search(
                client, c, path,
                budget=Budget(260), page_size=200, label="bmw-3series-under-25k",
            )
            results["search"] = show("search", c, "listing")
            listings = [r for r in c.rows if r["item_type"] == "listing"]
            if listings:
                ad_id = listings[0]["id"]
                seller_id = str(listings[0]["data"].get("sellerId"))
                summary = next(r for r in c.rows if r["item_type"] == "search_summary")
                print(f"  numResultsTotal={summary['data']['numResultsTotal']}"
                      f"  applied={summary['data']['appliedFilters']}"
                      f"  dropped={summary['data']['droppedFilters']}")
                print(f"  first: {listings[0]['data'].get('title')!r}"
                      f"  {listings[0]['data'].get('price',{}).get('gross')}"
                      f"  rating={listings[0]['data'].get('priceRating',{}).get('rating')}")
                print(f"  -> carrying ad_id={ad_id} seller_id={seller_id} into later modes")

        # Fall back to a known-live ad if search was skipped
        if ad_id is None and only not in (None, "search"):
            c0 = Collector()
            await run_search(
                client, c0,
                build_search_path({"vc": "Car", "ms": "3500;;21;", "sb": "doc", "od": "down"}),
                budget=Budget(6), page_size=20, label="seed",
            )
            seeds = [r for r in c0.rows if r["item_type"] == "listing"]
            if seeds:
                ad_id = seeds[0]["id"]
                seller_id = str(seeds[0]["data"].get("sellerId"))

        # 2. detail
        if only in (None, "detail") and ad_id:
            c = Collector()
            await run_detail(client, c, ad_id, budget=Budget(None))
            results["detail"] = show("detail", c, "listing_detail")
            d = next((r for r in c.rows if r["item_type"] == "listing_detail"), None)
            if d:
                desc = d["data"].get("htmlDescription") or ""
                print(f"  features={len(d['data'].get('features') or [])}"
                      f"  attributes={len(d['data'].get('attributes') or [])}"
                      f"  description={len(desc)} chars")

        # 3. dealer_contact
        if only in (None, "dealer_contact") and ad_id:
            c = Collector()
            await run_dealer_contact(client, c, ad_id, budget=Budget(None))
            results["dealer_contact"] = show("dealer_contact", c, "dealer_contact")
            row = next((r for r in c.rows if r["item_type"] == "dealer_contact"), None)
            if row:
                imprint = (row["data"].get("imprint") or "").strip().splitlines()
                print(f"  imprint first lines: {imprint[:3]}")

        # 4. dealer_inventory
        if only in (None, "dealer_inventory") and seller_id:
            c = Collector()
            await run_dealer_inventory(
                client, c, seller_id,
                budget=Budget(210), page_size=200, vehicle_category="Car",
            )
            results["dealer_inventory"] = show("dealer_inventory", c, "dealer_summary")
            s = next((r for r in c.rows if r["item_type"] == "dealer_summary"), None)
            if s:
                print(f"  dealer {seller_id} advertises {s['data']['adCount']} vehicles")

        # 5. similar_ads
        if only in (None, "similar_ads") and ad_id:
            c = Collector()
            await run_similar_ads(client, c, ad_id, budget=Budget(30))
            results["similar_ads"] = show("similar_ads", c, "similar_listing")

        # 6. market_count
        if only in (None, "market_count"):
            c = Collector()
            path = build_search_path(
                {"vc": "Car", "ms": "25200;;;", "ft": "DIESEL", "p": ":15000"}
            )
            await run_market_count(client, c, path, label="vw-diesel-under-15k", budget=Budget(None))
            results["market_count"] = show("market_count", c, "market_count")
            row = next((r for r in c.rows if r["item_type"] == "market_count"), None)
            if row:
                print(f"  count={row['data']['count']} filters={row['data']['filters']}")

        # 7. reference_data (capped -- the full walk is ~120 makes)
        if only in (None, "reference_data"):
            c = Collector()
            await run_reference_data(client, c, "Car", budget=Budget(4))
            results["reference_data"] = show("reference_data", c, "reference_make")
            rf = next((r for r in c.rows if r["item_type"] == "reference_filters"), None)
            if rf:
                print(f"  filter codes: {len(rf['data'])}  makes: {len(rf['data'].get('ms') or [])}")
            rm = next((r for r in c.rows if r["item_type"] == "reference_make"), None)
            if rm:
                print(f"  e.g. {rm['data']['makeName']} (id {rm['data']['makeId']}) "
                      f"ms={rm['data']['msExample']}")

        # 8. the decoy check -- legacy params must be reported as dropped
        if only in (None, "decoy"):
            c = Collector()
            await run_search(
                client, c,
                "/fahrzeuge/search.html?isSearchRequest=true&scopeId=C"
                "&makeModelVariant1.makeId=3500",
                budget=Budget(3), page_size=20, label="decoy-legacy-params",
            )
            s = next((r for r in c.rows if r["item_type"] == "search_summary"), None)
            dropped = s["data"]["droppedFilters"] if s else []
            print("\n--- decoy detection ---")
            print(f"  droppedFilters reported: {dropped}")
            results["decoy"] = bool(dropped)
            print(f"  => {'PASS' if dropped else 'FAIL (silent wrong-data bug not caught)'}")

    finally:
        await client.close()

    print("\n================ SUMMARY ================")
    for k, v in results.items():
        print(f"  {k:18s} {'PASS' if v else 'FAIL'}")
    print(f"  HTTP requests used: {client.requests_made}")
    print("=========================================")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
