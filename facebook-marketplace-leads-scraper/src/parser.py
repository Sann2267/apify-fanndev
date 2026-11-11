"""Parse Facebook Marketplace feeds and listing detail pages.

Listings come back whole here, unlike posts and reviews: a feed node owns its
title, price, location, photo and flags in one object. So the parser looks for
the key that identifies a listing (`marketplace_listing_title`) and reads the
node around it, wherever in the tree Facebook put it.

Two things the payload does *not* contain, logged out, and that this parser
therefore reports as null rather than inventing:

- **`marketplace_listing_seller` is null.** Facebook withholds the seller's
  identity from signed-out visitors on both the feed and the listing page. What
  it does publish is the location down to the city (and on the detail page the
  postal code and coordinates), which is what a broker or a price researcher is
  usually filtering on anyway.
- **`redacted_description` only exists on the detail page.** The feed carries no
  description at all, which is why fetching descriptions costs one extra request
  per listing and is opt-in.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import dedupe, iter_json_blocks, text_of, walk

ITEM_URL = "https://www.facebook.com/marketplace/item/{}/"
ITEM_ID = re.compile(r"/marketplace/item/(\d+)")
NUMERIC = re.compile(r"^\d{6,}$")
# "50K miles", "3 beds", "2 bathrooms"
MILES = re.compile(r"([\d.,]+)\s*K?\s*miles", re.I)
BEDS = re.compile(r"([\d.,]+)\s*beds?\b", re.I)
BATHS = re.compile(r"([\d.,]+)\s*bathrooms?\b", re.I)
YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def item_id(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if NUMERIC.match(value):
        return value
    match = ITEM_ID.search(value)
    return match.group(1) if match else None


def _iso(stamp: Any) -> str | None:
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return None
    if not 946_684_800 < stamp < 4_102_444_800:
        return None
    return (
        datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _age_days(stamp: Any) -> int | None:
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return None
    delta = datetime.now(tz=timezone.utc).timestamp() - stamp
    return int(delta // 86_400) if delta >= 0 else None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _subtitles(node: dict) -> list[str]:
    out = []
    for entry in node.get("custom_sub_titles_with_rendering_flags") or []:
        if isinstance(entry, dict) and isinstance(entry.get("subtitle"), str):
            out.append(entry["subtitle"])
    return out


def _from_subtitles(subtitles: list[str]) -> dict:
    """Mileage, bedrooms and bathrooms, which Facebook renders as free text.

    `"50K miles"` is the only place a vehicle's mileage appears in the feed, so
    it is parsed out and reported as a number alongside the original strings.
    """
    joined = " ".join(subtitles)
    out: dict[str, Any] = {"vehicleMileage": None, "bedrooms": None, "bathrooms": None}
    match = MILES.search(joined)
    if match:
        value = _float(match.group(1))
        if value is not None:
            # "50K miles" is 50,000; "50,000 miles" is already that.
            out["vehicleMileage"] = int(value * 1000) if "K" in joined[match.start():match.end()].upper() else int(value)
    match = BEDS.search(joined)
    if match:
        out["bedrooms"] = _float(match.group(1))
    match = BATHS.search(joined)
    if match:
        out["bathrooms"] = _float(match.group(1))
    return out


def parse_listing(node: dict) -> dict:
    """One feed listing node -> one flat record."""
    listing_id = str(node.get("id") or "") or None
    price = node.get("listing_price") or {}
    strike = node.get("strikethrough_price") or {}
    location = node.get("location") or {}
    geo = (location.get("reverse_geocode") or {}) if isinstance(location, dict) else {}
    photo = node.get("primary_listing_photo") or {}
    image = (photo.get("image") or {}) if isinstance(photo, dict) else {}
    subtitles = _subtitles(node)
    title = node.get("marketplace_listing_title")

    record = {
        "listingId": listing_id,
        "listingUrl": ITEM_URL.format(listing_id) if listing_id else None,
        "title": title,
        "customTitle": node.get("custom_title"),
        "priceText": price.get("formatted_amount"),
        "priceAmount": _float(price.get("amount")),
        "strikethroughPriceText": strike.get("formatted_amount") if isinstance(strike, dict) else None,
        "city": geo.get("city"),
        "state": geo.get("state"),
        "locationText": ((geo.get("city_page") or {}).get("display_name")
                         if isinstance(geo.get("city_page"), dict) else None),
        "createdAt": node.get("creation_time"),
        "createdAtIso": _iso(node.get("creation_time")),
        "ageDays": _age_days(node.get("creation_time")),
        "isSold": node.get("is_sold"),
        "isPending": node.get("is_pending"),
        "isLive": node.get("is_live"),
        "subtitles": subtitles,
        "deliveryTypes": node.get("delivery_types") or [],
        "categoryId": str(node.get("marketplace_listing_category_id") or "") or None,
        "photoUrl": image.get("uri"),
        "hasVideo": bool(node.get("listing_video")),
        # Facebook does not publish the seller to signed-out visitors. Reported
        # as null rather than omitted, so the absence is visible in the data.
        "sellerName": None,
        "sellerId": None,
        "originGroupName": ((node.get("origin_group") or {}).get("name")
                            if isinstance(node.get("origin_group"), dict) else None),
        "vehicleYear": None,
    }
    record.update(_from_subtitles(subtitles))

    if isinstance(title, str):
        match = YEAR.search(title)
        if match:
            record["vehicleYear"] = int(match.group(1))

    seller = node.get("marketplace_listing_seller")
    if isinstance(seller, dict):
        record["sellerName"] = seller.get("name")
        record["sellerId"] = seller.get("id")
    return record


def parse_feed(payload: Any) -> tuple[list[dict], str | None]:
    """Every listing in a feed payload, plus the cursor for the next page."""
    listings: list[dict] = []
    seen: set[str] = set()

    for node in walk(payload):
        if not isinstance(node.get("marketplace_listing_title"), str):
            continue
        record = parse_listing(node)
        key = record["listingId"] or record["title"]
        if not key or key in seen:
            continue
        seen.add(key)
        listings.append(record)

    cursor = None
    for node in walk(payload):
        info = node.get("page_info")
        if isinstance(info, dict) and info.get("end_cursor"):
            cursor = info["end_cursor"]
            if info.get("has_next_page"):
                break
    if cursor is None:
        # The category feed hands its cursor back on each edge rather than in a
        # page_info block, so the last edge's cursor is the one to continue from.
        cursors = [node["cursor"] for node in walk(payload)
                   if isinstance(node.get("cursor"), str) and node["cursor"]]
        cursor = cursors[-1] if cursors else None
    return listings, cursor


def parse_feed_html(html: str) -> tuple[list[dict], str | None]:
    listings: list[dict] = []
    seen: set[str] = set()
    cursor = None
    for block in iter_json_blocks(html):
        found, block_cursor = parse_feed(block)
        for record in found:
            key = record["listingId"] or record["title"]
            if key and key not in seen:
                seen.add(key)
                listings.append(record)
        if block_cursor:
            cursor = block_cursor
    return listings, cursor


VEHICLE_FIELDS = {
    "vehicle_make_display_name": "vehicleMake",
    "vehicle_model_display_name": "vehicleModel",
    "vehicle_exterior_color": "vehicleExteriorColor",
    "vehicle_interior_color": "vehicleInteriorColor",
    "vehicle_fuel_type": "vehicleFuelType",
    "vehicle_transmission_type": "vehicleTransmissionType",
    "vehicle_identification_number": "vehicleVin",
    "vehicle_number_of_owners": "vehicleOwners",
}


def parse_detail(html: str, listing_id: str) -> dict:
    """The listing page's own fields: description, coordinates, condition, specs.

    Only the target listing's node is used. A listing page also renders ~19
    *related* listings, and reading the first node that happens to match would
    silently describe somebody else's item.
    """
    out: dict[str, Any] = {
        "description": None,
        "condition": None,
        "latitude": None,
        "longitude": None,
        "postalCode": None,
        "countryCode": None,
        "locationText": None,
        "currency": None,
        "isShippingOffered": None,
        "detailFound": False,
    }
    out.update({name: None for name in VEHICLE_FIELDS.values()})

    for block in iter_json_blocks(html):
        for node in walk(block):
            if str(node.get("id") or "") != listing_id:
                continue
            if "redacted_description" not in node and "listing_price" not in node:
                continue
            out["detailFound"] = True

            description = node.get("redacted_description")
            if out["description"] is None and isinstance(description, dict):
                out["description"] = description.get("text")
            if out["condition"] is None and isinstance(node.get("condition"), str):
                out["condition"] = node["condition"]
            if out["locationText"] is None:
                out["locationText"] = text_of(node.get("location_text"))
            price = node.get("listing_price")
            if out["currency"] is None and isinstance(price, dict):
                out["currency"] = price.get("currency")
            if out["isShippingOffered"] is None and "is_shipping_offered" in node:
                out["isShippingOffered"] = node.get("is_shipping_offered")

            location = node.get("location")
            if isinstance(location, dict):
                if out["latitude"] is None and isinstance(location.get("latitude"), (int, float)):
                    out["latitude"] = location["latitude"]
                    out["longitude"] = location.get("longitude")
                detailed = location.get("reverse_geocode_detailed")
                if isinstance(detailed, dict):
                    out["postalCode"] = out["postalCode"] or detailed.get("postal_code_trimmed")
                    out["countryCode"] = out["countryCode"] or detailed.get("country_alpha_two")

            for source, target in VEHICLE_FIELDS.items():
                if out[target] is None and node.get(source) not in (None, ""):
                    out[target] = node[source]

    # Coordinates and vehicle specs are published on nodes that sit beside the
    # listing rather than on it, so a second pass fills only what is still empty
    # and only from nodes that name this listing.
    if out["detailFound"] and out["latitude"] is None:
        for block in iter_json_blocks(html):
            for node in walk(block):
                target = node.get("marketplace_listing_renderable_target")
                if not isinstance(target, dict) or str(target.get("id") or "") != listing_id:
                    continue
                location = target.get("location")
                if isinstance(location, dict):
                    out["latitude"] = location.get("latitude")
                    out["longitude"] = location.get("longitude")
    return out


def matches_filters(listing: dict, filters: dict) -> bool:
    if filters.get("excludeSold") and listing.get("isSold"):
        return False
    needle = (filters.get("titleContains") or "").strip().lower()
    if needle:
        haystack = f"{listing.get('title') or ''} {listing.get('customTitle') or ''}".lower()
        if needle not in haystack:
            return False
    for key, bound, compare in (
        ("minPrice", filters.get("minPrice"), lambda a, b: a >= b),
        ("maxPrice", filters.get("maxPrice"), lambda a, b: a <= b),
    ):
        if bound is not None:
            price = listing.get("priceAmount")
            # A listing with no readable price cannot be shown to sit inside the
            # range, so it is dropped rather than admitted on a guess.
            if price is None or not compare(price, float(bound)):
                return False
    max_age = filters.get("maxAgeDays")
    if max_age is not None:
        age = listing.get("ageDays")
        if not isinstance(age, int) or age > int(max_age):
            return False
    return True


def summarise(listings: Iterable[dict]) -> dict:
    listings = list(listings)
    prices = sorted(p for p in (l.get("priceAmount") for l in listings) if isinstance(p, float))
    cities = {l.get("city") for l in listings if l.get("city")}
    sold = sum(1 for l in listings if l.get("isSold"))
    median = prices[len(prices) // 2] if prices else None
    return {
        "listingsCollected": len(listings),
        "distinctCities": len(cities),
        "soldListings": sold,
        "withPrice": len(prices),
        "minPrice": prices[0] if prices else None,
        "medianPrice": median,
        "maxPrice": prices[-1] if prices else None,
        "sellerNamesAvailable": sum(1 for l in listings if l.get("sellerName")),
    }
