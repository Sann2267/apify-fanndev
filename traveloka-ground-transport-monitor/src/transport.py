"""Resolve bus locations and pull intercity departures with fares."""

from __future__ import annotations

import datetime as dt
import logging
import statistics

from src.client import TravelokaError
from src.constants import (
    BUS_AUTOCOMPLETE,
    BUS_INVENTORY,
    DEDUPE_MODES,
    HARD_MAX_DEPARTURES,
    REFERER_BUS,
)

logger = logging.getLogger(__name__)


def _num(value):
    if value in (None, "", "null"):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return int(out) if out.is_integer() else out


def _money(block) -> tuple[float | None, str | None]:
    """Unwrap Traveloka's {currencyValue:{currency, amount, nullOrEmpty}} shape."""
    if not isinstance(block, dict):
        return None, None
    value = block.get("currencyValue") or {}
    if value.get("nullOrEmpty"):
        return None, value.get("currency")
    return _num(value.get("amount")), value.get("currency")


async def resolve_location(client, query: str) -> dict | None:
    """Look a city, terminal or landmark up in the bus autocomplete."""
    query = (query or "").strip()
    if not query:
        return None
    path, domain = BUS_AUTOCOMPLETE
    payload = await client.call_async(path, domain, {"query": query}, REFERER_BUS)

    rows = [item for group in payload.get("groups") or []
            for item in group.get("items") or []
            if isinstance(item, dict) and item.get("code")]
    if not rows:
        return None

    # Prefer a whole city over one terminal: a city code covers every departure
    # point in it, which is what a route monitor wants.
    rows.sort(key=lambda r: 0 if (r.get("type") or "").endswith("CITY_GEO") else 1)
    best = rows[0]
    return {
        "code": best["code"],
        "type": best.get("type") or "CITY_GEO",
        "label": best.get("label") or best.get("searchFormLabel"),
        "subLabel": best.get("subLabel"),
        "query": query,
    }


def _point(block: dict) -> dict:
    block = block or {}
    geo = block.get("geoPoint") or {}
    # localTime nests two levels deeper than the rest of the payload:
    # localTime.specificDate.{monthDayYear,hourMinute}, all values as strings.
    local_time = block.get("localTime") or {}
    specific = local_time.get("specificDate") or {}
    day_parts = specific.get("monthDayYear") or {}
    time_parts = specific.get("hourMinute") or {}

    time_text = None
    try:
        time_text = f"{int(time_parts['hour']):02d}:{int(time_parts['minute']):02d}"
    except (KeyError, TypeError, ValueError):
        time_text = None

    date_text = None
    try:
        date_text = dt.date(int(day_parts["year"]), int(day_parts["month"]),
                            int(day_parts["day"])).isoformat()
    except (KeyError, TypeError, ValueError):
        date_text = None
    return {
        "name": block.get("name"),
        "address": block.get("address"),
        "cityName": block.get("cityName"),
        "cityCode": block.get("cityCode"),
        "pointCode": block.get("routePointCode"),
        "latitude": _num(geo.get("lat")),
        "longitude": _num(geo.get("lon")),
        "timeZone": local_time.get("timeZoneId"),
        "date": date_text,
        "time": time_text,
    }


def shape_departure(entry: dict, route: dict, travel_date: str) -> dict:
    fare, currency = _money(entry.get("fare"))
    old_fare, _ = _money(entry.get("oldFare"))
    child_fare, _ = _money(entry.get("childFare"))
    infant_fare, _ = _money(entry.get("infantFare"))
    duration = entry.get("duration") or {}
    rating = entry.get("ratingScore") or {}
    availability = entry.get("availability") or {}

    hours = _num(duration.get("hour")) or 0
    minutes = _num(duration.get("minute")) or 0

    discount_pct = None
    if old_fare and fare and old_fare > fare:
        discount_pct = round((old_fare - fare) / old_fare * 100, 2)

    origin = _point(entry.get("originRoutePointDetail"))
    destination = _point(entry.get("destinationRoutePointDetail"))

    return {
        "recordType": "DEPARTURE",
        "searchDate": travel_date,
        "routeQuery": route["label"],
        "originQuery": route["originQuery"],
        "destinationQuery": route["destinationQuery"],
        "routeSequence": entry.get("routeSequence"),
        "productType": entry.get("productType"),
        "operatorName": entry.get("providerName"),
        "operatorId": entry.get("providerId"),
        "fleetName": entry.get("fleetName"),
        "busType": entry.get("busType"),
        "seatClass": entry.get("seatClass"),
        "seatSubClass": entry.get("seatSubClass"),
        "seatLayout": entry.get("seatLayout"),
        "seatCapacity": _num(entry.get("seatCapacity")),
        "seatsAvailable": _num(entry.get("numOfSeatsAvailable")),
        "availabilityStatus": availability.get("status"),
        "fare": fare,
        "originalFare": old_fare,
        "discountPercent": discount_pct,
        "childFare": child_fare,
        "infantFare": infant_fare,
        "currency": currency,
        "promoLabel": entry.get("promoLabel"),
        "durationMinutes": int(hours) * 60 + int(minutes),
        "departureDate": origin["date"],
        "departureTime": origin["time"],
        "timeZone": origin["timeZone"],
        "arrivalDate": destination["date"],
        "arrivalTime": destination["time"],
        "pickupPointName": origin["name"],
        "pickupPointAddress": origin["address"],
        "pickupCity": origin["cityName"],
        "pickupLatitude": origin["latitude"],
        "pickupLongitude": origin["longitude"],
        "dropoffPointName": destination["name"],
        "dropoffPointAddress": destination["address"],
        "dropoffCity": destination["cityName"],
        "dropoffLatitude": destination["latitude"],
        "dropoffLongitude": destination["longitude"],
        "facilities": [f.get("label") for f in entry.get("facilities") or []
                       if isinstance(f, dict) and f.get("label")],
        "operatorRating": _num(rating.get("rating")),
        "operatorRatingScale": _num(rating.get("maxRating")),
        "operatorReviewCount": _num(rating.get("count")),
        "routeId": entry.get("routeId"),
        "skuId": entry.get("skuId"),
        "busTripCode": entry.get("busTripCode"),
        "inventoryId": entry.get("inventoryId"),
    }


def _dedupe_key(departure: dict, mode: str):
    if mode == "trip":
        # One trip sold from many pickup points repeats with the same trip code.
        return (departure.get("busTripCode"), departure.get("departureTime"),
                departure.get("operatorId"))
    if mode == "operator":
        return (departure.get("operatorId"), departure.get("departureTime"),
                departure.get("seatClass"))
    return None


async def search_departures(client, route: dict, travel_date: dt.date,
                            adults: int, max_departures: int, dedupe: str,
                            product_types: list[str]):
    """One search = one city pair on one date. Returns shaped departures."""
    if dedupe not in DEDUPE_MODES:
        dedupe = "trip"
    path, domain = BUS_INVENTORY

    payload = await client.call_async(
        path, domain,
        {
            "originCode": route["originCode"],
            "originType": route["originType"],
            "destinationCode": route["destinationCode"],
            "destinationType": route["destinationType"],
            "departureDate": {"year": travel_date.year, "month": travel_date.month,
                              "day": travel_date.day},
            "roundTrip": False,
            "numAdult": adults,
            "currency": client.currency,
        },
        REFERER_BUS, timeout=180)

    status = payload.get("status")
    if status != "SUCCESSFUL":
        raise TravelokaError(
            f"Bus search returned status {status!r}: "
            f"{payload.get('errorMessage') or 'no detail'}")

    raw = payload.get("departInventories") or []
    logger.info("%s on %s: %d raw inventories from Traveloka.",
                route["label"], travel_date.isoformat(), len(raw))

    out: list[dict] = []
    seen = set()
    wanted = {p.upper() for p in product_types} if product_types else None
    cap = min(max_departures, HARD_MAX_DEPARTURES)

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if wanted and (entry.get("productType") or "").upper() not in wanted:
            continue
        shaped = shape_departure(entry, route, travel_date.isoformat())
        key = _dedupe_key(shaped, dedupe)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        out.append(shaped)
        if len(out) >= cap:
            logger.info("Reached the %d-departure cap for %s on %s.",
                        cap, route["label"], travel_date.isoformat())
            break

    return out, len(raw)


def summarise_route(departures: list[dict], route: dict, travel_date: str,
                    raw_count: int) -> dict:
    fares = [d["fare"] for d in departures if d.get("fare")]
    operators: dict[str, dict] = {}
    for dep in departures:
        name = dep.get("operatorName") or "unknown"
        bucket = operators.setdefault(name, {
            "operatorName": name,
            "operatorId": dep.get("operatorId"),
            "departures": 0,
            "fares": [],
            "rating": dep.get("operatorRating"),
            "reviewCount": dep.get("operatorReviewCount"),
            "productTypes": set(),
        })
        bucket["departures"] += 1
        if dep.get("fare"):
            bucket["fares"].append(dep["fare"])
        if dep.get("productType"):
            bucket["productTypes"].add(dep["productType"])

    operator_rows = []
    for bucket in operators.values():
        bucket_fares = bucket.pop("fares")
        bucket["productTypes"] = sorted(bucket["productTypes"])
        bucket["minFare"] = min(bucket_fares) if bucket_fares else None
        bucket["maxFare"] = max(bucket_fares) if bucket_fares else None
        bucket["averageFare"] = (round(statistics.fmean(bucket_fares), 2)
                                 if bucket_fares else None)
        operator_rows.append(bucket)
    operator_rows.sort(key=lambda row: (row["minFare"] is None, row["minFare"]))

    seats = [d["seatsAvailable"] for d in departures
             if d.get("seatsAvailable") is not None]
    discounted = [d for d in departures if d.get("discountPercent")]

    return {
        "recordType": "ROUTE_SUMMARY",
        "searchDate": travel_date,
        "routeQuery": route["label"],
        "originQuery": route["originQuery"],
        "destinationQuery": route["destinationQuery"],
        "originCode": route["originCode"],
        "destinationCode": route["destinationCode"],
        "departuresReturned": len(departures),
        "inventoriesBeforeDedupe": raw_count,
        "operatorCount": len(operator_rows),
        "minFare": min(fares) if fares else None,
        "maxFare": max(fares) if fares else None,
        "averageFare": round(statistics.fmean(fares), 2) if fares else None,
        "totalSeatsAvailable": sum(seats) if seats else None,
        "departuresOnPromo": len(discounted),
        "operators": operator_rows,
    }
