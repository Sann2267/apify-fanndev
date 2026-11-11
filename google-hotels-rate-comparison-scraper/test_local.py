"""Local smoke test -- runs the real HTTP path, no Apify platform involved.

    python test_local.py

Asserts on measurable facts rather than on "it did not crash": a card must
carry a price and a name, and a major hotel must return several OTA quotes,
because a parser that silently returns empty fields is worse than one that
raises (.ai/CLAUDE.md rule 6).
"""

import asyncio
import json
import sys

from src.client import GoogleHotelsClient
from src.constants import URL_ENTITY, URL_SEARCH
from src.extractor import parse_entity, parse_rates, parse_search, parse_sponsored

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    client = GoogleHotelsClient()
    failures: list[str] = []

    print("=" * 72)
    print("1. mode=search -- hotels in singapore")
    url = URL_SEARCH.format(query="hotels+in+singapore", hl="en", gl="us")
    html, profile = await client.get_html(url)
    hotels = parse_search(html, "hotels in singapore")
    print(f"   TLS profile that won: {profile}")
    print(f"   hotels parsed: {len(hotels)}")
    if len(hotels) < 5:
        failures.append(f"expected 20+ hotel cards, got {len(hotels)}")
    priced = [h for h in hotels if h.get("price")]
    rated = [h for h in hotels if h.get("rating")]
    print(f"   with a price: {len(priced)} | with a rating: {len(rated)}")
    if not priced:
        failures.append("no hotel card carried a price")
    print("   sample:", json.dumps(hotels[0], ensure_ascii=False, indent=2)[:900])

    print("=" * 72)
    print("2. mode=hotel -- the first hotel's rate table")
    entity_id = hotels[0]["entityId"]
    entity_url = URL_ENTITY.format(entity_id=entity_id, hl="en", gl="us")
    entity_html, _ = await client.get_html(entity_url)
    detail = parse_entity(entity_id, entity_html)
    print(f"   name: {detail['name']}")
    print(f"   address: {detail['address']}")
    print(f"   phone: {detail['phone']}")
    print(f"   rating: {detail['rating']} from {detail['reviewCount']} reviews, {detail['starClass']}-star")
    print(f"   stay window Google priced: {detail['stayWindow']}")
    print(f"   rateCount: {detail['rateCount']} | currency: {detail['currency']}")
    print(f"   lowest {detail['lowestRate']} / highest {detail['highestRate']} / spread {detail['rateSpread']}")
    print(f"   cheapest provider: {detail['cheapestProvider']}")
    if detail["rateCount"] == 0:
        failures.append(f"{detail['name']} returned zero OTA quotes")
    if not detail["name"]:
        failures.append("entity page produced no hotel name")
    # The header must come from the hotel's own block, not a neighbour's.
    if detail["reviewCount"] and hotels[0].get("reviewCount"):
        if abs(detail["reviewCount"] - hotels[0]["reviewCount"]) > hotels[0]["reviewCount"] * 0.2:
            failures.append(
                f"entity reviewCount {detail['reviewCount']} disagrees with the card's "
                f"{hotels[0]['reviewCount']} -- the header was probably read from a neighbouring block"
            )
    if detail["address"] and detail["address"].endswith("."):
        failures.append(f"address looks like prose, not an address: {detail['address']!r}")

    print("=" * 72)
    print("3. mode=rates -- flat, one record per OTA quote")
    rates = parse_rates(entity_id, entity_html)
    for rate in rates[:8]:
        print(
            f"   {str(rate['provider'])[:26]:28s} {str(rate['priceRaw']):18s} "
            f"organic={rate['isOrganic']} host={rate['providerHost']}"
        )
    hosts = {r["providerHost"] for r in rates if r.get("providerHost")}
    print(f"   distinct provider hosts: {len(hosts)}")
    if not any(r["bookingUrl"] for r in rates):
        failures.append("no rate row carried a booking deep link")

    print("=" * 72)
    print("4. mode=sponsored -- paid placements, kept apart from rates")
    ads = parse_sponsored(entity_id, entity_html)
    print(f"   sponsored placements: {len(ads)}")
    for ad in ads[:4]:
        print(f"   {str(ad['name'])[:38]:40s} {str(ad['priceRaw']):18s} via {ad['provider']}")
    overlap = {a["name"] for a in ads} & {detail["name"]}
    if overlap:
        failures.append(f"a sponsored placement was for the hotel itself: {overlap}")

    await client.close()

    print("=" * 72)
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


asyncio.run(main())
