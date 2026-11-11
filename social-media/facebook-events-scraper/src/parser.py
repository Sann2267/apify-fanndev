"""Parse Facebook event payloads.

Events, unlike posts and videos, arrive whole: one node carries the name, the
URL, the date sentence, the place, the price line, the cover photo and the
online flag together, marked `"__typename": "Event"`. So the parser finds nodes
by that marker and reads them directly.

The date needs care. Facebook publishes two things:

    "day_time_sentence": "Sun, 20 Sep at 16:00 EDT"
    "start_timestamp": 1789934400

The sentence is what a human sees, abbreviated and localised, with no year on
near-term events. The timestamp is exact. Both are emitted, because a sentence
cannot be sorted and a timestamp cannot be read aloud -- and the sentence is the
only one of the two that survives on the page events tab, where
`start_timestamp` is absent.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import iter_json_blocks, text_of, walk

EVENT_URL = "https://www.facebook.com/events/{}/"
EVENT_ID = re.compile(r"/events/(\d{6,})")
PAGE_SLUG = re.compile(r"facebook\.com/(?:pg/)?([^/?#]+)", re.I)
RESERVED = {"events", "profile.php", "people", "groups", "marketplace", "watch",
            "ads", "search", "photo", "reel"}
# "1 going", "23 interested", "1.2K going"
GOING = re.compile(r"([\d.,]+\s*[KMB]?)\s+going", re.I)
INTERESTED = re.compile(r"([\d.,]+\s*[KMB]?)\s+interested", re.I)


def event_id(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit() and len(value) >= 6:
        return value
    match = EVENT_ID.search(value)
    return match.group(1) if match else None


def page_ref(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if event_id(value):
        return None
    match = PAGE_SLUG.match(value) or PAGE_SLUG.search(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    if not value or value.lower() in RESERVED:
        return None
    return value


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


def _count(label: str | None) -> int | None:
    from src.fbcore import parse_count

    return parse_count(label) if label else None


def _place(node: dict) -> dict:
    place = node.get("event_place")
    out = {"placeName": None, "placeAddress": None, "placeId": None,
           "latitude": None, "longitude": None, "city": None, "country": None}
    if not isinstance(place, dict):
        return out
    name = place.get("name")
    out["placeName"] = name if isinstance(name, str) and name else None
    # A FreeformPlace has no separate name: `contextual_name` is the whole
    # address line the organiser typed.
    out["placeAddress"] = place.get("contextual_name")
    out["placeId"] = place.get("id") or None
    location = place.get("location")
    if isinstance(location, dict):
        out["latitude"] = location.get("latitude")
        out["longitude"] = location.get("longitude")
        geocode = location.get("reverse_geocode")
        if isinstance(geocode, dict):
            out["city"] = geocode.get("city")
        out["country"] = location.get("country") or None
    if out["placeName"] is None and isinstance(out["placeAddress"], str):
        # Use the first comma-separated segment as a venue label; it is what the
        # organiser typed first and is usually the venue.
        first = out["placeAddress"].split(",")[0].strip()
        out["placeName"] = first or None
    return out


def parse_event(node: dict) -> dict:
    url = node.get("url") or node.get("eventUrl")
    eid = str(node.get("id") or "") or None
    if not url and eid:
        url = EVENT_URL.format(eid)

    social = node.get("social_context")
    social_text = text_of(social) if social is not None else None
    cover = node.get("cover_photo") or {}
    photo = cover.get("photo") if isinstance(cover, dict) else None
    photo = photo if isinstance(photo, dict) else {}
    ticketing = node.get("ticketing_context_row") or {}
    creator = node.get("event_creator") or {}
    creator = creator if isinstance(creator, dict) else {}
    start = node.get("start_timestamp")

    record = {
        "eventId": eid,
        "name": node.get("name"),
        "eventUrl": url,
        "dayTimeSentence": node.get("day_time_sentence"),
        "startTimestamp": start if isinstance(start, int) else None,
        "startsAtIso": _iso(start),
        "isOnline": node.get("is_online") if "is_online" in node
        else node.get("is_online_or_detected_online"),
        "isPast": node.get("is_past"),
        "isHappeningNow": node.get("is_happening_now"),
        "isCanceled": node.get("is_canceled"),
        "eventKind": node.get("event_kind"),
        "priceRangeText": ticketing.get("price_range_text")
        if isinstance(ticketing, dict) else None,
        "hostName": creator.get("name"),
        "hostUrl": creator.get("url"),
        "hostId": creator.get("id"),
        "coverPhotoUrl": photo.get("uri") or (node.get("typeaheadProfilePicture") or {}).get("uri"),
        # Facebook's own alt text for the cover image. It is machine-generated
        # and often contains the poster's headline text, which is the closest
        # thing to a description the public payload carries.
        "coverPhotoCaption": photo.get("accessibility_caption"),
        "attendanceText": social_text,
        "goingCount": None,
        "interestedCount": None,
    }
    record.update(_place(node))

    if social_text:
        match = GOING.search(social_text)
        if match:
            record["goingCount"] = _count(match.group(1))
        match = INTERESTED.search(social_text)
        if match:
            record["interestedCount"] = _count(match.group(1))
    return record


def merge_event(target: dict, other: dict) -> None:
    """Fill gaps in `target` from `other`, never overwriting a value already there."""
    for key, value in other.items():
        if value in (None, "", []):
            continue
        if target.get(key) in (None, "", []):
            target[key] = value


def parse_events(payload: Any) -> list[dict]:
    """Every event in a payload, merged by id.

    Facebook renders the same event at two levels of detail in one response. The
    rich node carries `day_time_sentence`, `start_timestamp`, `event_place` and
    the cover photo; a thin node carries only `id`, `name`, `url` and a thumbnail.
    Which one appears first varies between responses, and some responses carry
    only thin nodes.

    Taking the first node that matches therefore produces events with null dates
    and places for no reason the data explains. Merging every node that shares an
    id, gaps-only, keeps whatever detail the response actually contained.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []
    for node in walk(payload):
        if node.get("__typename") != "Event" or not node.get("name"):
            continue
        record = parse_event(node)
        key = record["eventId"] or record["eventUrl"] or record["name"]
        if not key:
            continue
        if key not in merged:
            merged[key] = record
            order.append(key)
        else:
            merge_event(merged[key], record)
    return [merged[key] for key in order]


def parse_events_html(html: str) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for block in iter_json_blocks(html):
        for record in parse_events(block):
            key = record["eventId"] or record["name"]
            if not key:
                continue
            if key not in merged:
                merged[key] = record
                order.append(key)
            else:
                merge_event(merged[key], record)
    return [merged[key] for key in order]


def is_detailed(event: dict) -> bool:
    """Whether this event came back with more than a name and a link."""
    return bool(event.get("dayTimeSentence") or event.get("startTimestamp")
                or event.get("placeAddress") or event.get("placeName"))


def next_cursor(payload: Any) -> str | None:
    for node in walk(payload):
        info = node.get("page_info")
        if isinstance(info, dict) and info.get("end_cursor") and info.get("has_next_page"):
            return info["end_cursor"]
    return None


def cursor_from_html(html: str) -> str | None:
    for block in iter_json_blocks(html):
        found = next_cursor(block)
        if found:
            return found
    return None


def matches_filters(event: dict, filters: dict) -> bool:
    if filters.get("excludePast") and event.get("isPast"):
        return False
    if filters.get("excludeCanceled") and event.get("isCanceled"):
        return False
    if filters.get("onlyOnline") and not event.get("isOnline"):
        return False
    if filters.get("onlyInPerson") and event.get("isOnline"):
        return False
    needle = (filters.get("nameContains") or "").strip().lower()
    if needle and needle not in (event.get("name") or "").lower():
        return False
    place = (filters.get("placeContains") or "").strip().lower()
    if place:
        haystack = " ".join(
            str(event.get(field) or "") for field in ("placeName", "placeAddress", "city")
        ).lower()
        if place not in haystack:
            return False
    after = filters.get("startsAfterEpoch")
    if isinstance(after, int):
        start = event.get("startTimestamp")
        # The page events tab publishes the date sentence but no timestamp, so a
        # date filter cannot judge those events. They are dropped rather than
        # admitted on a guess -- the log says so when it happens.
        if not isinstance(start, int) or start < after:
            return False
    before = filters.get("startsBeforeEpoch")
    if isinstance(before, int):
        start = event.get("startTimestamp")
        if not isinstance(start, int) or start > before:
            return False
    return True


def summarise(events: Iterable[dict]) -> dict:
    events = list(events)
    timestamps = [e["startTimestamp"] for e in events if isinstance(e.get("startTimestamp"), int)]
    going = [e["goingCount"] for e in events if isinstance(e.get("goingCount"), int)]
    return {
        "eventsCollected": len(events),
        "online": sum(1 for e in events if e.get("isOnline")),
        "inPerson": sum(1 for e in events if e.get("isOnline") is False),
        "withTimestamp": len(timestamps),
        "withPlace": sum(1 for e in events if e.get("placeAddress") or e.get("placeName")),
        "withAttendance": len(going),
        "totalGoing": sum(going) if going else None,
        "earliestIso": _iso(min(timestamps)) if timestamps else None,
        "latestIso": _iso(max(timestamps)) if timestamps else None,
    }
