"""Resolve airports and pull the two un-gated flight price surfaces."""

from __future__ import annotations

import datetime as dt
import logging
import re
import statistics

from src.constants import (
    AIRPORT_SEARCH,
    MAX_GRID_CELLS,
    MONTHLY_CHEAPEST,
    PRICE_TABLE,
    REFERER_FLIGHT,
)

logger = logging.getLogger(__name__)

_IATA = re.compile(r"^[A-Z]{3,4}$")


def _num(value):
    if value in (None, "", "null"):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return int(out) if out.is_integer() else out


def _date_obj(day: dt.date) -> dict:
    return {"year": day.year, "month": day.month, "day": day.day}


async def resolve_airport(client, query: str) -> dict | None:
    """Turn free text or an IATA code into the code+type the price APIs want.

    A 3-letter uppercase token is taken as a code and used directly; anything
    else is looked up. Traveloka distinguishes an `AIRPORT` (DPS) from an `AREA`
    that groups several airports (JKTA covers CGK and HLP), and the price table
    rejects `AREA`, so we always resolve to a concrete airport there.
    """
    query = (query or "").strip()
    if not query:
        return None

    path, domain = AIRPORT_SEARCH
    payload = await client.call_async(
        path, domain,
        {"query": query, "filters": {}, "frequentAirport": [],
         "originAirport": None, "showTags": False},
        REFERER_FLIGHT)

    for section in payload.get("sections") or []:
        for result in section.get("results") or []:
            code = result.get("iataCode") or result.get("code")
            if not code:
                continue
            area_code = result.get("areaCode")
            display = result.get("displayData") or {}
            return {
                "code": code,
                # A row whose code equals its areaCode is a multi-airport area.
                "type": "AREA" if area_code == code and not result.get("iataCode")
                        else "AIRPORT",
                "name": display.get("title") or result.get("location"),
                "description": display.get("description"),
                "country": result.get("country"),
                "query": query,
            }

    if _IATA.match(query.upper()):
        logger.info("No autocomplete row for %r; using it as a raw code.", query)
        return {"code": query.upper(), "type": "AIRPORT", "name": None,
                "description": None, "country": None, "query": query}
    return None


async def monthly_curve(client, origin: dict, destination: dict,
                        journey_type: str, start: dt.date) -> list[dict]:
    """Cheapest fare per month for the next 12 months -- one request per route."""
    path, domain = MONTHLY_CHEAPEST
    payload = await client.call_async(
        path, domain,
        {
            "originCode": origin["code"].upper(),
            "originAirportType": origin["type"],
            "destinationCode": destination["code"].upper(),
            "destinationAirportType": destination["type"],
            "journeyType": journey_type,
            "searchDate": _date_obj(start),
        },
        REFERER_FLIGHT)

    out: list[dict] = []
    for entry in payload.get("monthlyCheapestPrices") or []:
        date = entry.get("date") or {}
        fare = ((entry.get("cheapestPrice") or {}).get("currencyValue") or {})
        amount = _num(fare.get("amount"))
        try:
            month_start = dt.date(int(date["year"]), int(date["month"]), 1)
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "month": month_start.strftime("%Y-%m"),
            "monthStart": month_start.isoformat(),
            "cheapestFare": amount,
            "currency": fare.get("currency") or client.currency,
            "isCheapestMonth": entry.get("priceType") == "CHEAPEST",
            "label": entry.get("cheapestLabel"),
            "hasFare": amount is not None and amount > 0,
        })
    return out


def _grid_chunks(depart_days: int, return_days: int) -> list[tuple[int, int]]:
    """Split a requested window into blocks of at most `MAX_GRID_CELLS` cells."""
    depart_days = max(1, depart_days)
    return_days = max(1, return_days)
    if depart_days * return_days <= MAX_GRID_CELLS:
        return [(0, depart_days)]

    # Keep the return span whole where possible and walk the depart axis.
    block = max(1, MAX_GRID_CELLS // min(return_days, MAX_GRID_CELLS))
    chunks = []
    for depart_offset in range(0, depart_days, block):
        chunks.append((depart_offset, min(block, depart_days - depart_offset)))
    return [(offset, size) for offset, size in chunks]


async def price_grid(client, origin: dict, destination: dict,
                     depart_start: dt.date, depart_days: int,
                     return_start: dt.date, return_days: int,
                     seat_class: str, adults: int, children: int,
                     infants: int, locale: str) -> list[dict]:
    """Round-trip depart x return fare matrix, chunked under the 100-cell cap."""
    path, domain = PRICE_TABLE
    rows: list[dict] = []

    for offset, size in _grid_chunks(depart_days, return_days):
        window_start = depart_start + dt.timedelta(days=offset)
        window_end = window_start + dt.timedelta(days=size - 1)
        payload = await client.call_async(
            path, domain,
            {
                "sourceAirportOrArea": origin["code"].upper(),
                "sourceAirportType": origin["type"],
                "destinationAirportOrArea": destination["code"].upper(),
                "destinationAirportType": destination["type"],
                "locale": locale.replace("-", "_"),
                "currency": client.currency,
                "departFlightDate": {"startDate": _date_obj(window_start),
                                     "endDate": _date_obj(window_end)},
                "returnFlightDate": {
                    "startDate": _date_obj(return_start),
                    "endDate": _date_obj(return_start
                                         + dt.timedelta(days=return_days - 1))},
                "seatPublishedClass": seat_class,
                "numSeats": {"numAdults": adults, "numChildren": children,
                             "numInfants": infants},
            },
            REFERER_FLIGHT)

        cells = payload.get("cheapestFareSummaries") or {}
        if not cells:
            logger.info("No fares for depart %s..%s.", window_start, window_end)
        for key, cell in cells.items():
            # Keys look like "10-20_10-26": depart MM-DD, then return MM-DD.
            depart_key, _, return_key = key.partition("_")
            fare = cell.get("cheapestFare") or {}
            amount = _num(fare.get("amount"))
            rows.append({
                "departDate": _key_to_date(depart_key, window_start).isoformat()
                if _key_to_date(depart_key, window_start) else None,
                "returnDate": _key_to_date(return_key, return_start).isoformat()
                if _key_to_date(return_key, return_start) else None,
                "fare": amount,
                "currency": fare.get("currency") or client.currency,
                "displayPrice": cell.get("displayPrice"),
                "isCheapestOfGrid": cell.get("displayType") == "HIGHLIGHT_CHEAP",
            })
    return rows


def _key_to_date(key: str, near: dt.date) -> dt.date | None:
    """Grid keys carry MM-DD only; pick the year that sits nearest the window."""
    try:
        month, day = (int(part) for part in key.split("-"))
    except (ValueError, AttributeError):
        return None
    for year in (near.year, near.year + 1, near.year - 1):
        try:
            candidate = dt.date(year, month, day)
        except ValueError:
            continue
        if abs((candidate - near).days) <= 200:
            return candidate
    return None


def summarise(monthly: list[dict], grid: list[dict],
              threshold: float | None) -> dict:
    month_fares = [m["cheapestFare"] for m in monthly
                   if m.get("cheapestFare")]
    grid_fares = [g["fare"] for g in grid if g.get("fare")]
    all_fares = month_fares + grid_fares

    cheapest_month = min((m for m in monthly if m.get("cheapestFare")),
                         key=lambda m: m["cheapestFare"], default=None)
    cheapest_cell = min((g for g in grid if g.get("fare")),
                        key=lambda g: g["fare"], default=None)

    lowest = min(all_fares) if all_fares else None
    return {
        "lowestFare": lowest,
        "highestFare": max(all_fares) if all_fares else None,
        "averageFare": round(statistics.fmean(all_fares), 2) if all_fares else None,
        "cheapestMonth": cheapest_month["month"] if cheapest_month else None,
        "cheapestMonthFare": cheapest_month["cheapestFare"] if cheapest_month else None,
        "cheapestDepartDate": cheapest_cell["departDate"] if cheapest_cell else None,
        "cheapestReturnDate": cheapest_cell["returnDate"] if cheapest_cell else None,
        "cheapestGridFare": cheapest_cell["fare"] if cheapest_cell else None,
        "quotesCollected": len(all_fares),
        "priceThreshold": threshold,
        "belowThreshold": bool(threshold and lowest is not None and lowest <= threshold),
    }
