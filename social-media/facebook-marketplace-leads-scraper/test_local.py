"""Offline + live checks for the Marketplace scraper.

    python test_local.py            # live: a city feed, a search, one listing page
    python test_local.py --offline  # parser and URL building only
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession  # noqa: E402
from src.marketplace import build_url, collect, enrich  # noqa: E402
from src.parser import item_id, matches_filters, parse_listing, summarise  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def offline_checks() -> bool:
    ok = True
    ok &= check("item id from URL",
                item_id("https://www.facebook.com/marketplace/item/1128881020071910/")
                == "1128881020071910")
    ok &= check("item id from bare number", item_id("1128881020071910") == "1128881020071910")

    url = build_url({"city": "nyc", "category": "vehicles", "minPrice": 20000})
    ok &= check("city feed URL", url.endswith("/marketplace/nyc/vehicles?minPrice=20000"), url)
    url = build_url({"city": "jakarta", "search": "iphone", "maxPrice": 900})
    ok &= check("city search URL",
                "/marketplace/jakarta/search/?query=iphone" in url and "maxPrice=900" in url, url)
    url = build_url({"category": "propertyforsale"})
    ok &= check("no-city URL falls back to /category/",
                url.endswith("/marketplace/category/propertyforsale"), url)

    node = {
        "id": "1128881020071910",
        "marketplace_listing_title": "2013 Subaru BRZ",
        "custom_title": "2013 Subaru brz",
        "listing_price": {"formatted_amount": "$200,000", "amount": "200000.00"},
        "location": {"reverse_geocode": {"city": "Hayward", "state": "CA",
                                         "city_page": {"display_name": "Hayward, California"}}},
        "creation_time": 1_789_067_301,
        "custom_sub_titles_with_rendering_flags": [{"subtitle": "50K miles"}],
        "delivery_types": ["IN_PERSON"],
        "is_sold": False,
        "primary_listing_photo": {"image": {"uri": "https://scontent/x.jpg"}},
        "marketplace_listing_seller": None,
    }
    listing = parse_listing(node)
    ok &= check("title and price", listing["title"] == "2013 Subaru BRZ"
                and listing["priceAmount"] == 200000.0)
    ok &= check("city parsed", listing["city"] == "Hayward")
    ok &= check("mileage parsed from the subtitle", listing["vehicleMileage"] == 50000,
                str(listing["vehicleMileage"]))
    ok &= check("year parsed from the title", listing["vehicleYear"] == 2013)
    ok &= check("seller reported as null, not omitted", "sellerName" in listing
                and listing["sellerName"] is None)

    ok &= check("price filter keeps in-range",
                matches_filters(listing, {"minPrice": 1000, "maxPrice": 300000}) is True)
    ok &= check("listing with no price fails a price filter",
                matches_filters({"priceAmount": None}, {"minPrice": 1}) is False)
    stats = summarise([listing])
    ok &= check("summary", stats["listingsCollected"] == 1 and stats["medianPrice"] == 200000.0,
                json.dumps(stats))
    return ok


async def live_checks() -> bool:
    ok = True
    async with FacebookSession(log=Log()) as session:
        print("\n-- a city feed, paginated --")
        query = {"city": "nyc", "category": "vehicles", "search": None,
                 "minPrice": None, "maxPrice": None, "sortBy": None, "radiusKm": None}
        listings, meta = await collect(session, query, 40, log=Log())
        ok &= check("listings returned", len(listings) >= 20,
                    f"{len(listings)} in {meta['requestsMade']} request(s)")
        ok &= check("pagination went past the rendered page", len(listings) > 24,
                    str(len(listings)))
        cities = {l["city"] for l in listings if l["city"]}
        ok &= check("results are local to the city slug",
                    bool(cities) and len(cities) >= 2, ", ".join(sorted(cities)[:5]))
        priced = [l for l in listings if l["priceAmount"] is not None]
        ok &= check("prices parsed", len(priced) >= 15, f"{len(priced)} with a price")

        print("\n-- a numeric location id returns the WRONG city, which is why it is rejected --")
        by_slug, _ = await collect(session, {**query, "city": "nyc"}, 24)
        by_id, _ = await collect(session, {**query, "city": "109571519060768"}, 24)
        slug_cities = {l["state"] for l in by_slug if l["state"]}
        id_cities = {l["state"] for l in by_id if l["state"]}
        ok &= check("slug and numeric id disagree", slug_cities != id_cities,
                    f"slug={sorted(slug_cities)[:3]} id={sorted(id_cities)[:3]}")

        print("\n-- a search, and one listing page --")
        search_listings, _ = await collect(
            session,
            {**query, "category": None, "search": "iphone", "minPrice": 500, "maxPrice": 900},
            24,
        )
        ok &= check("search returns listings", len(search_listings) >= 5,
                    str(len(search_listings)))
        prices = [l["priceAmount"] for l in search_listings if l["priceAmount"] is not None]
        ok &= check("minPrice/maxPrice honoured by Facebook",
                    bool(prices) and min(prices) >= 500 and max(prices) <= 900,
                    f"{min(prices) if prices else None}-{max(prices) if prices else None}")

        if listings:
            detail = await enrich(session, listings[0])
            ok &= check("listing page returns detail", detail.get("detailFound") is True,
                        json.dumps({k: detail.get(k) for k in
                                    ("condition", "latitude", "postalCode", "currency")},
                                   ensure_ascii=False))
            print("    description:",
                  (detail.get("description") or "")[:90] or "(none published)")
    return ok


def main() -> int:
    print("== offline ==")
    ok = offline_checks()
    if "--offline" not in sys.argv:
        print("\n== live ==")
        ok = asyncio.run(live_checks()) and ok
    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
