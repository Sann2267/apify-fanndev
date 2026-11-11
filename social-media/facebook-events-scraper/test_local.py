"""Offline + live checks for the events scraper.

    python test_local.py            # live: two searches and a page events tab
    python test_local.py --offline  # parser only, no network
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from src.events import EventsUnavailable, page_events, search_events  # noqa: E402
from src.fbcore import FacebookSession  # noqa: E402
from src.main import epoch_from_date, read_input  # noqa: E402
from src.parser import (  # noqa: E402
    event_id,
    matches_filters,
    page_ref,
    parse_events,
    summarise,
)


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
    ok &= check("event id from URL",
                event_id("https://www.facebook.com/events/1089275243587546/")
                == "1089275243587546")
    ok &= check("page slug parsed", page_ref("https://www.facebook.com/MTV/events") == "MTV")
    ok &= check("events path not treated as a page", page_ref("facebook.com/events/123456") is None)
    ok &= check("date parsed", epoch_from_date("2026-01-01", "startsAfter") == 1767225600)

    terms, slugs = read_input({"searchTerms": ["yoga"], "locations": ["new york", "boston"],
                               "pages": ["MTV"]})
    ok &= check("locations expand the search terms",
                terms == ["yoga new york", "yoga boston"], str(terms))
    ok &= check("pages read", slugs == ["MTV"])
    terms_only, _ = read_input({"locations": ["jakarta"]})
    ok &= check("a location alone is a valid search", terms_only == ["jakarta"])

    payload = {"node": {
        "__typename": "Event",
        "id": "1089275243587546",
        "name": "Therapeutic Yoga: Movement Lab",
        "url": "https://www.facebook.com/events/1089275243587546/",
        "day_time_sentence": "Sun, 20 Sep at 16:00 EDT",
        "start_timestamp": 1_789_934_400,
        "is_online": False,
        "is_past": False,
        "event_kind": "PUBLIC_TYPE",
        "event_place": {"__typename": "FreeformPlace",
                        "contextual_name": "149 Irving Ave , Brooklyn, NY, United States, New York 11237",
                        "id": "123"},
        "ticketing_context_row": {"price_range_text": None},
        "social_context": {"text": "1 going"},
        "cover_photo": {"photo": {"uri": "https://img/cover.jpg",
                                  "accessibility_caption": "May be an image of dancing"}},
    }}
    events = parse_events(payload)
    ok &= check("event parsed", len(events) == 1)
    event = events[0]
    ok &= check("name and url", event["name"].startswith("Therapeutic Yoga"))
    ok &= check("timestamp converted", event["startsAtIso"] == "2026-09-20T20:00:00Z",
                str(event["startsAtIso"]))
    ok &= check("sentence kept alongside the timestamp",
                event["dayTimeSentence"] == "Sun, 20 Sep at 16:00 EDT")
    ok &= check("freeform place becomes address + venue label",
                event["placeAddress"].startswith("149 Irving Ave")
                and event["placeName"] == "149 Irving Ave", str(event["placeName"]))
    ok &= check("attendance parsed", event["goingCount"] == 1, str(event["goingCount"]))
    ok &= check("cover caption kept", bool(event["coverPhotoCaption"]))

    ok &= check("date filter drops an event with no timestamp",
                matches_filters({"startTimestamp": None}, {"startsAfterEpoch": 1}) is False)
    ok &= check("onlyOnline drops an in-person event",
                matches_filters(event, {"onlyOnline": True}) is False)
    ok &= check("summary", summarise([event])["inPerson"] == 1)
    return ok


async def live_checks() -> bool:
    ok = True
    async with FacebookSession(log=Log()) as session:
        print("\n-- text search, with the city in the query --")
        events, meta = await search_events(session, "yoga new york", 20, log=Log())
        ok &= check("search returns events", len(events) >= 4,
                    f"{len(events)} in {meta['requestsMade']} request(s)")
        named = [e for e in events if e["name"]]
        ok &= check("events are named", len(named) == len(events),
                    ", ".join(e["name"][:28] for e in events[:3]))
        placed = [e for e in events if e["placeAddress"] or e["placeName"]]
        ok &= check("places present", len(placed) >= 2, f"{len(placed)} with a place")
        timed = [e for e in events if e["startsAtIso"]]
        ok &= check("exact start times present", len(timed) >= 2, f"{len(timed)} with a timestamp")
        if events:
            print("    sample:", json.dumps(
                {k: events[0].get(k) for k in
                 ("name", "dayTimeSentence", "startsAtIso", "placeAddress", "isOnline",
                  "goingCount", "eventUrl")}, ensure_ascii=False)[:320])

        print("\n-- the city alone is a valid query --")
        jakarta, _ = await search_events(session, "konser jakarta", 10)
        ok &= check("localised search works", len(jakarta) >= 1,
                    ", ".join(e["name"][:26] for e in jakarta[:3]))

        print("\n-- a page's own events tab --")
        page, _ = await page_events(session, "MTV", 12, log=Log())
        ok &= check("page events returned", len(page) >= 3, str(len(page)))
        hosts = [e for e in page if e["hostName"]]
        ok &= check("host named on page events", len(hosts) >= 1,
                    str([e["hostName"] for e in page[:3]]))
        ok &= check(
            "page-tab events legitimately lack an exact timestamp",
            any(e["dayTimeSentence"] and not e["startsAtIso"] for e in page),
            str([(e["dayTimeSentence"], e["startsAtIso"]) for e in page[:2]]),
        )

        print("\n-- a page that publishes no events --")
        try:
            await page_events(session, "zz-not-a-real-page-98765", 5)
            ok &= check("missing page raises", False, "no exception")
        except EventsUnavailable as exc:
            ok &= check("missing page raises EventsUnavailable", True, str(exc)[:60])
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
