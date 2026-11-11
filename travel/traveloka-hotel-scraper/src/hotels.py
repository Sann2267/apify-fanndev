"""Fetch and shape one property: profile, rooms, nightly price calendar, reviews."""

from __future__ import annotations

import calendar as calmod
import datetime as dt
import logging
import statistics

from src.client import GateError, TravelokaError
from src.constants import (
    CC_GUARANTEE_OPTIONS_CALENDAR,
    DEFAULT_IMAGE_TYPE,
    HOTEL_ASSETS,
    HOTEL_DETAIL,
    MAX_CALENDAR_MONTHS,
    PRICE_CALENDAR,
    RATE_TYPES,
    REFERER_DETAIL,
    REVIEW_CONFIG_ID,
    REVIEW_PRODUCT_TYPE,
    REVIEW_SUMMARY,
    ROOMS_STATIC,
)

logger = logging.getLogger(__name__)

# Saturday and Sunday nights are the weekend premium most revenue managers watch.
WEEKEND_WEEKDAYS = {4, 5}  # Friday-night and Saturday-night stays


def _num(value):
    """Traveloka returns numbers as strings almost everywhere."""
    if value in (None, "", "null"):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return int(out) if out.is_integer() else out


def months_from(start: dt.date, count: int) -> list[tuple[int, int]]:
    out = []
    year, month = start.year, start.month
    for _ in range(min(count, MAX_CALENDAR_MONTHS)):
        out.append((year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


async def fetch_profile(client, hotel_id: str) -> dict:
    """Property profile: name, address, coordinates, star rating, facilities.

    Sending `userSearchPreferences` here makes the backend answer 400 -- the
    detail endpoint only wants the ID and a currency.
    """
    path, domain = HOTEL_DETAIL
    return await client.call_async(
        path, domain, {"hotelId": hotel_id, "currency": client.currency},
        REFERER_DETAIL)


async def fetch_rooms(client, hotel_id: str, stay: dict) -> list[dict]:
    """Room inventory (names, photos, amenities, bedding, size).

    This is the *static* room endpoint. Its dynamic twin carries nightly rates
    but sits behind the AWS WAF CAPTCHA, so rates come from the calendar instead.
    """
    path, domain = ROOMS_STATIC
    payload = await client.call_async(
        path, domain,
        {"hotelId": hotel_id, "userSearchPreferences": stay,
         "currency": client.currency},
        REFERER_DETAIL)
    return payload.get("roomList") or []


async def fetch_calendar(client, hotel_id: str, year: int, month: int,
                         adults: int, rooms: int) -> list[dict]:
    """Nightly rates for one calendar month -- one request, up to 31 prices."""
    path, domain = PRICE_CALENDAR
    payload = await client.call_async(
        path, domain,
        {
            "hotelId": hotel_id,
            "ccGuaranteeOptions": CC_GUARANTEE_OPTIONS_CALENDAR,
            "numAdults": adults, "numChildren": 0, "numInfants": 0,
            "numRooms": rooms,
            "yearMonth": {"year": str(year), "month": f"{month:02d}"},
            "currency": client.currency,
            "userInfoSpec": None,
            "sid": "ALTERNATIVE",
            "rateTypes": RATE_TYPES,
        },
        REFERER_DETAIL)

    results = payload.get("results") or {}
    no_allotment = payload.get("noAllotmentResults") or {}
    days_in_month = calmod.monthrange(year, month)[1]

    nights: list[dict] = []
    for day in range(1, days_in_month + 1):
        key = str(day)
        entry = results.get(key) or {}
        blocked = no_allotment.get(key) or {}
        price = (entry.get("price") or {}) if isinstance(entry, dict) else {}
        date = dt.date(year, month, day)
        amount = _num(price.get("amount"))
        status = entry.get("availabilityStatus") or blocked.get("availabilityStatus")
        if amount is None and not status:
            # Past dates and unreleased months come back as bare skeletons.
            continue
        # An UNAVAILABLE night is returned as amount 0 with an empty display
        # price. Left as 0 it drags the minimum and both averages to nonsense.
        if amount == 0:
            amount = None
        nights.append({
            "date": date.isoformat(),
            "dayOfWeek": date.strftime("%A"),
            "isWeekendNight": date.weekday() in WEEKEND_WEEKDAYS,
            "price": amount,
            "currency": price.get("currency") or client.currency,
            "displayPrice": entry.get("displayPrice"),
            "availabilityStatus": status,
            "isCheapestOfMonth": entry.get("bestDateStatus") == "HIGHLIGHT_CHEAP",
        })
    return nights


def summarise_prices(nights: list[dict]) -> dict:
    """Weekday vs weekend comparison -- the point of pulling a whole month."""
    priced = [n for n in nights if n["price"] is not None]
    weekend = [n["price"] for n in priced if n["isWeekendNight"]]
    weekday = [n["price"] for n in priced if not n["isWeekendNight"]]

    def avg(values):
        return round(statistics.fmean(values), 2) if values else None

    weekday_avg, weekend_avg = avg(weekday), avg(weekend)
    premium = None
    if weekday_avg and weekend_avg:
        premium = round((weekend_avg - weekday_avg) / weekday_avg * 100, 2)

    cheapest = min(priced, key=lambda n: n["price"]) if priced else None
    dearest = max(priced, key=lambda n: n["price"]) if priced else None
    return {
        "nightsPriced": len(priced),
        "nightsUnavailable": sum(
            1 for n in nights
            if n["availabilityStatus"] in ("NO_ALLOTMENT", "UNAVAILABLE")),
        "minPrice": cheapest["price"] if cheapest else None,
        "minPriceDate": cheapest["date"] if cheapest else None,
        "maxPrice": dearest["price"] if dearest else None,
        "maxPriceDate": dearest["date"] if dearest else None,
        "averagePrice": avg([n["price"] for n in priced]),
        "weekdayAveragePrice": weekday_avg,
        "weekendAveragePrice": weekend_avg,
        "weekendPremiumPercent": premium,
    }


async def fetch_review_summary(client, hotel_id: str) -> dict:
    path, domain = REVIEW_SUMMARY
    payload = await client.call_async(
        path, domain,
        {"configId": REVIEW_CONFIG_ID, "objectId": hotel_id,
         "productType": REVIEW_PRODUCT_TYPE, "withDistributions": True,
         "withAISummary": True, "origin": "FALLBACK"},
        REFERER_DETAIL)
    aggregate = payload.get("reviewAggregate") or {}
    return {
        "rating": _num(aggregate.get("overallRating")),
        "ratingScale": _num(aggregate.get("maximumRating")),
        "reviewCount": _num(aggregate.get("count")),
        "ratingLabel": aggregate.get("textRating"),
    }


async def fetch_images(client, hotel_id: str) -> list[str]:
    path, domain = HOTEL_ASSETS
    payload = await client.call_async(
        path, domain,
        {"hotelIds": [hotel_id], "imageType": DEFAULT_IMAGE_TYPE},
        REFERER_DETAIL)
    assets = payload if isinstance(payload, list) else payload.get("assets") or []
    return [a.get("url") for a in assets if isinstance(a, dict) and a.get("url")]


def shape_room(room: dict) -> dict:
    size = room.get("hotelRoomSizeDisplay") or {}
    smoking = room.get("smokingPreferences") or {}
    bedding = room.get("bedArrangements") or {}
    return {
        "roomId": room.get("hotelRoomId"),
        "name": room.get("name"),
        "description": room.get("description"),
        "baseOccupancy": _num(room.get("baseOccupancy")),
        "bedTypes": room.get("hotelBedType") or [],
        "bedroomSummary": bedding.get("bedroomSummary"),
        "roomSizeValue": _num(size.get("value")),
        "roomSizeUnit": size.get("unit"),
        "smokingPolicy": smoking.get("type"),
        "view": room.get("roomDisplayView"),
        "wifiIncluded": room.get("isWifiIncluded"),
        "amenities": room.get("amenitiesIncluded") or [],
        "images": [u for u in (room.get("roomImages") or []) if isinstance(u, str)],
    }


def shape_profile(profile: dict, hotel_id: str, locale: str) -> dict:
    geo = profile.get("hotelGEO") or {}
    props = profile.get("properties") or {}
    seo = profile.get("seoInfo") or {}
    assets = profile.get("assets") or []
    return {
        "hotelId": profile.get("id") or hotel_id,
        "name": profile.get("name"),
        "displayName": profile.get("displayName"),
        "url": (seo.get("url") or "").replace("m.traveloka.com",
                                              "www.traveloka.com") or None,
        "accommodationType": profile.get("accomPropertyType"),
        "accommodationTypeCode": profile.get("accomType"),
        "starRating": _num(profile.get("starRating")),
        "address": profile.get("address"),
        "city": profile.get("city"),
        "province": profile.get("province"),
        "country": profile.get("country"),
        "postalCode": profile.get("postalCode"),
        "latitude": _num(profile.get("latitude")),
        "longitude": _num(profile.get("longitude")),
        "areaName": geo.get("name"),
        "areaGeoId": geo.get("geoId"),
        "checkInTime": props.get("checkInTime"),
        "checkOutTime": props.get("checkOutTime"),
        "facilityCodes": profile.get("showedFacilityTypes") or [],
        "facilityNames": profile.get("showedFacilityTypesString") or [],
        "supportedRateTypes": profile.get("supportedRateTypes") or [],
        "images": [a.get("url") for a in assets
                   if isinstance(a, dict) and a.get("url")][:30],
        "locale": locale,
    }


async def scrape_hotel(client, hotel_id: str, options: dict) -> dict:
    """Assemble one output record. Partial failures are reported, not fatal."""
    record: dict = {
        "hotelId": hotel_id,
        "recordType": "PROPERTY",
        "scrapedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "warnings": [],
    }

    try:
        profile = await fetch_profile(client, hotel_id)
    except GateError as exc:
        record.update({"recordType": "GATED", "error": str(exc)})
        return record
    except TravelokaError as exc:
        record.update({"recordType": "ERROR", "error": str(exc)})
        return record

    # A nonexistent ID does not 404: the endpoint echoes the ID back with every
    # other field null. Treat a nameless profile as "no such property".
    if not profile.get("name"):
        record.update({"recordType": "NOT_FOUND",
                       "error": f"No property exists with ID {hotel_id}."})
        return record

    record.update(shape_profile(profile, hotel_id, client.locale))

    if options.get("includeReviewSummary", True):
        try:
            record["reviewSummary"] = await fetch_review_summary(client, hotel_id)
        except TravelokaError as exc:
            record["warnings"].append(f"review summary unavailable: {exc}")

    if options.get("includeRooms", True):
        try:
            rooms = await fetch_rooms(client, hotel_id, options["stay"])
            record["rooms"] = [shape_room(r) for r in rooms]
            record["roomCount"] = len(rooms)
        except TravelokaError as exc:
            record["warnings"].append(f"room list unavailable: {exc}")

    if options.get("includeCalendar", True):
        nights: list[dict] = []
        for year, month in options["months"]:
            try:
                nights.extend(await fetch_calendar(
                    client, hotel_id, year, month,
                    options["adults"], options["rooms"]))
            except TravelokaError as exc:
                record["warnings"].append(f"calendar {year}-{month:02d}: {exc}")
        record["priceCalendar"] = nights
        record["priceSummary"] = summarise_prices(nights)
        record["currency"] = client.currency

    return record
