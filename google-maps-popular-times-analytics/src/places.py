"""Parse Google's positional place record into a flat lead.

The same parser serves both surfaces, because a `tbm=map` search entry and a
`/maps/preview/place` response carry the identical positional shape. That is
what keeps this actor cheap: a search page yields 20 complete leads, so the
per-place detail call is only needed for places supplied directly by URL or ID.

Positional arrays punish defensive coding: a short array is normal, but a
*shifted* one silently yields wrong values. So the container is validated
strictly while individual optional fields are read tolerantly through `_at`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.constants import (
    P_ADDRESS,
    P_ADDRESS_PARTS,
    P_ADDRESS_WITH_NAME,
    P_CATEGORIES,
    P_COORDS,
    P_DESCRIPTION,
    P_FEATURE_ID,
    P_GOOGLE_SLUG,
    P_HOURS,
    P_LANGUAGE,
    P_NAME,
    P_PHONE,
    P_PLACE_ID,
    P_PLUS_CODE,
    P_RATING_BLOCK,
    P_REGION,
    P_THUMBNAIL,
    P_TIMEZONE,
    P_WEBSITE,
    PLACE_DETAIL_IDX,
    SEARCH_ENTRY_PLACE_IDX,
    SEARCH_RESULTS_PATH,
)

REVIEW_COUNT_RE = re.compile(r"([\d,.  ]+)\s+review", re.IGNORECASE)
# Google pads clock strings with narrow/no-break spaces ("10 AM-8 PM").
NARROW_SPACES = dict.fromkeys(map(ord, "   "), " ")


def _at(seq: Any, index: int, default: Any = None) -> Any:
    if not isinstance(seq, (list, tuple)) or index >= len(seq):
        return default
    value = seq[index]
    return default if value is None else value


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.translate(NARROW_SPACES).strip()
    return value


def extract_search_places(payload: Any) -> list:
    """Pull the place records out of a tbm=map response.

    The first entry of the results array is the query echo, not a place, and
    entries can carry no place payload at all (ads, "missing place" prompts),
    so entries are selected by having a real record rather than by position.
    """
    node: Any = payload
    for index in SEARCH_RESULTS_PATH:
        if not isinstance(node, list) or index >= len(node):
            return []
        node = node[index]
    if not isinstance(node, list):
        return []

    places = []
    for entry in node:
        record = _at(entry, SEARCH_ENTRY_PLACE_IDX)
        if isinstance(record, list) and _at(record, P_FEATURE_ID) and _at(record, P_NAME):
            places.append(record)
    return places


def extract_detail_place(payload: Any) -> Any:
    """Pull the place record out of a /maps/preview/place response."""
    record = _at(payload, PLACE_DETAIL_IDX)
    if isinstance(record, list) and _at(record, P_FEATURE_ID):
        return record
    return None


def _parse_phone(raw: Any) -> dict:
    """review[178] = [pretty, [[local,1],[intl,2]], null, e164, null, [tel:...]]."""
    if not isinstance(raw, list):
        return {"phone": None, "phoneE164": None, "phoneLocal": None}
    block = _at(raw, 0)
    if isinstance(block, list):
        block = _at(block, 0)
    pretty = block if isinstance(block, str) else None
    e164 = None
    local = None
    first = _at(raw, 0)
    if isinstance(first, list):
        pretty = _at(first, 0) if isinstance(_at(first, 0), str) else pretty
        e164 = _at(first, 3) if isinstance(_at(first, 3), str) else None
        for variant in _at(first, 1, []) or []:
            if isinstance(variant, list) and isinstance(_at(variant, 0), str):
                if _at(variant, 1) == 1:
                    local = variant[0]
    return {
        "phone": _clean(pretty),
        "phoneE164": e164,
        "phoneLocal": _clean(local),
    }


def _parse_website(raw: Any) -> dict:
    if not isinstance(raw, list):
        return {"website": None, "websiteDomain": None}
    url = _at(raw, 0)
    return {
        "website": url if isinstance(url, str) and url.startswith("http") else None,
        "websiteDomain": _at(raw, 1),
    }


def _parse_rating(raw: Any) -> dict:
    """place[4] = [.., [reviews_url, "826 reviews", ..], .., rating, count].

    Read positionally, not by type. Two traps make type-sniffing wrong here:
    a whole-number rating arrives as an int (5, not 5.0) and is indistinguishable
    from a small review count, and Google varies how much of this block it sends
    between requests -- sometimes the whole thing, sometimes just [.. , rating].
    """
    if not isinstance(raw, list):
        return {"rating": None, "reviewsCount": None, "reviewsUrl": None}

    rating = _at(raw, 7)
    if not isinstance(rating, (int, float)) or isinstance(rating, bool) or not 0 < rating <= 5:
        rating = None

    count = _at(raw, 8)
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        count = None

    reviews_url = None
    block = _at(raw, 3)
    if isinstance(block, list):
        for inner in block:
            if not isinstance(inner, str):
                continue
            if inner.startswith("http") and reviews_url is None:
                reviews_url = inner
            elif count is None:
                match = REVIEW_COUNT_RE.search(inner)
                if match:
                    # Locale-formatted: "1.139 reviews" / "1,139 reviews".
                    digits = re.sub(r"[^\d]", "", match.group(1))
                    count = int(digits) if digits else None

    return {"rating": float(rating) if rating is not None else None,
            "reviewsCount": count, "reviewsUrl": reviews_url}


def _is_day_entry(entry: Any) -> bool:
    """Recognise an opening-hours entry by SHAPE, not by slot or language.

    A day entry looks like ["Wednesday", 3, [2026, 9, 16], [["10 AM-8 PM", ...]], ...].
    Matching on the [year, month, day] triple plus a leading string makes this
    work whatever `hl` is set to, and survives Google moving the block -- which
    it demonstrably does: slot 203 holds the schedule in some responses and
    nothing in others for the very same place.
    """
    if not isinstance(entry, list) or len(entry) < 4:
        return False
    if not isinstance(entry[0], str) or not entry[0].strip():
        return False
    date = entry[2]
    if not (isinstance(date, list) and len(date) == 3
            and all(isinstance(v, int) for v in date) and 1900 < date[0] < 2200):
        return False
    return isinstance(entry[3], list)


def _find_hours_container(record: Any, _depth: int = 0) -> list | None:
    """Locate the richest list of day entries anywhere in the record."""
    if _depth > 6 or not isinstance(record, list):
        return None
    best: list | None = None
    if record and all(_is_day_entry(e) for e in record if e is not None):
        entries = [e for e in record if _is_day_entry(e)]
        if entries:
            best = entries
    for child in record:
        found = _find_hours_container(child, _depth + 1)
        if found and (best is None or len(found) > len(best)):
            best = found
    return best


def _parse_hours(raw: Any) -> dict:
    """Return [{day, hours:[...]}] for as much of the week as Google supplied."""
    days: list[dict] = []
    open_now = None
    entries = _find_hours_container(raw) or []
    for entry in entries:
        day = _clean(entry[0])
        spans = entry[3]
        texts = []
        if isinstance(spans, list):
            for span in spans:
                text = _at(span, 0)
                if isinstance(text, str):
                    texts.append(_clean(text))
        if texts and not any(d["day"] == day for d in days):
            days.append({"day": day, "hours": texts})

    # The open/closed status line sits beside the schedule, not inside it.
    if isinstance(raw, list):
        flat = str(raw)
        for marker in ("Open · Closes", "Closed · Opens", "Open 24 hours",
                       "Temporarily closed", "Permanently closed"):
            if marker in flat:
                open_now = marker
                break
    return {"openingHours": days, "openNow": open_now}


def _parse_plus_code(raw: Any) -> str | None:
    """Plus code lives in a nested label block; find the first code-shaped token."""
    text = str(raw)
    match = re.search(r'"([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,4})"', text)
    return match.group(1) if match else None


def parse_place(record: Any) -> dict | None:
    """Turn one positional place record into a flat lead."""
    if not isinstance(record, list):
        return None
    feature_id = _at(record, P_FEATURE_ID)
    name = _at(record, P_NAME)
    if not feature_id or not name:
        return None

    coords = _at(record, P_COORDS, [])
    categories = _at(record, P_CATEGORIES, []) or []
    if isinstance(categories, str):
        categories = [categories]

    lead = {
        "name": _clean(name),
        "featureId": feature_id,
        "placeId": _at(record, P_PLACE_ID),
        "googleSlug": _at(record, P_GOOGLE_SLUG),
        "categories": [c for c in categories if isinstance(c, str)],
        "primaryCategory": next((c for c in categories if isinstance(c, str)), None),
        "address": _clean(_at(record, P_ADDRESS)),
        "addressParts": [p for p in (_at(record, P_ADDRESS_PARTS, []) or []) if isinstance(p, str)],
        "addressWithName": _clean(_at(record, P_ADDRESS_WITH_NAME)),
        "region": _clean(_at(record, P_REGION)),
        "latitude": _at(coords, 2),
        "longitude": _at(coords, 3),
        "plusCode": _parse_plus_code(_at(record, P_PLUS_CODE)),
        "timezone": _at(record, P_TIMEZONE),
        "language": _at(record, P_LANGUAGE),
        "description": _clean(_at(record, P_DESCRIPTION, [None])[0]
                              if isinstance(_at(record, P_DESCRIPTION), list)
                              else _at(record, P_DESCRIPTION)),
        "thumbnailUrl": _at(record, P_THUMBNAIL),
        **_parse_phone(_at(record, P_PHONE)),
        **_parse_website(_at(record, P_WEBSITE)),
        **_parse_rating(_at(record, P_RATING_BLOCK)),
        **_parse_hours(record),
    }
    lead["googleMapsUrl"] = (
        f"https://www.google.com/maps/place/data=!4m2!3m1!1s{feature_id}?hl=en"
    )
    # Seed the enrichment fields for every lead, including ones with no website.
    # A field that exists on some rows and is absent on others makes CSV columns
    # shift and downstream schemas unstable.
    lead.setdefault("emails", [])
    lead.setdefault("socialProfiles", {})
    lead.setdefault("websitePhones", [])
    lead.setdefault("enrichmentStatus", "no_website" if not lead.get("website") else "not_attempted")
    lead.setdefault("enrichmentPagesFetched", 0)
    lead.setdefault("enrichmentFinalUrl", None)
    # How complete the opening-hours schedule is, so consumers can tell a
    # genuinely one-day listing from a search-result record that only ever
    # carries today's hours (see fetchPlaceDetails in the README).
    lead["openingHoursComplete"] = len(lead.get("openingHours") or []) >= 7
    return lead
