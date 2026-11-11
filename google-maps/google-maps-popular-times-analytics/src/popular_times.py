"""Parse Google's popular-times histogram and live occupancy.

Shape, mapped from live data (see CRAWLING_METHOD.md):

    [ [7, null, 1],                                    # a day with no data
      [1, [[6, 0,  "",                      "", "6 am", null, "6a"],
           [7, 20, "Usually not too busy",  "", "7 am", null, "6a"],
           ...], 0],
      ... ]

Each hour entry is [hour24, occupancyPercent, label, "", displayHour, null, bucket].
Days are numbered 1=Monday .. 7=Sunday -- verified two ways: the container's
sibling "current day" value was 3 on a Wednesday, and the only day carrying no
data was 7 for a gym whose opening hours show Sunday closed.

The container is found **structurally**, never by slot index. Google moves this
block between responses exactly as it moves opening hours, so an index-based
read silently reports "no popular times" for places that have it.
"""

from __future__ import annotations

from typing import Any

# 1 = Monday, matching ISO weekday numbering.
DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
             5: "Friday", 6: "Saturday", 7: "Sunday"}

# Text Google attaches to the live reading. "Now: …" means it is only projecting
# from the usual curve; anything "… than usual" means a real live measurement.
LIVE_TEXT_SUFFIX = "than usual"
USUAL_TEXT_PREFIX = "Now:"


def _is_hour_entry(entry: Any) -> bool:
    return (
        isinstance(entry, list)
        and len(entry) >= 5
        and isinstance(entry[0], int) and 0 <= entry[0] <= 23
        and isinstance(entry[1], int) and 0 <= entry[1] <= 100
        and isinstance(entry[2], str)
        and isinstance(entry[4], str)
    )


def _is_day_group(group: Any) -> bool:
    if not (isinstance(group, list) and len(group) >= 2):
        return False
    if not (isinstance(group[0], int) and 1 <= group[0] <= 7):
        return False
    hours = group[1]
    if hours is None:          # a day Google has no data for -- still a valid group
        return True
    return isinstance(hours, list) and bool(hours) and all(_is_hour_entry(h) for h in hours)


def find_container(record: Any, _depth: int = 0) -> list | None:
    """Locate the list of day-groups anywhere inside a place record."""
    if _depth > 8 or not isinstance(record, list):
        return None
    if (len(record) >= 2 and all(_is_day_group(g) for g in record)
            and any(isinstance(g[1], list) for g in record)):
        return record
    for child in record:
        found = find_container(child, _depth + 1)
        if found is not None:
            return found
    return None


def _find_parent(record: Any, container: list, _depth: int = 0) -> list | None:
    """The live reading lives beside the container, in its parent list."""
    if _depth > 8 or not isinstance(record, list):
        return None
    for child in record:
        if child is container:
            return record
        found = _find_parent(child, container, _depth + 1)
        if found is not None:
            return found
    return None


def _parse_live(parent: Any) -> dict:
    """Read the live block that sits next to the histogram.

    The parent looks like [container, currentDay, null, 1, currentHour, null,
    statusText, [hour, livePercent]] -- the final pair is present only when
    Google actually has a live measurement.
    """
    live: dict = {
        "liveOccupancyPercent": None,
        "liveStatusText": None,
        "liveHour": None,
        "hasLiveData": False,
        "currentDay": None,
        "currentHour": None,
    }
    if not isinstance(parent, list):
        return live

    for index, value in enumerate(parent):
        if isinstance(value, str) and value.strip():
            live["liveStatusText"] = value.strip()
        elif (isinstance(value, list) and len(value) == 2
              and all(isinstance(v, int) for v in value)
              and 0 <= value[0] <= 23 and 0 <= value[1] <= 100):
            live["liveHour"], live["liveOccupancyPercent"] = value
            live["hasLiveData"] = True
        elif isinstance(value, int) and index == 1 and 1 <= value <= 7:
            live["currentDay"] = value
        elif isinstance(value, int) and index == 4 and 0 <= value <= 23:
            live["currentHour"] = value

    text = live["liveStatusText"] or ""
    # "Now: Usually as busy as it gets" is a projection from the weekly curve,
    # not a live reading -- do not let it masquerade as one.
    if text.startswith(USUAL_TEXT_PREFIX) and not live["hasLiveData"]:
        live["hasLiveData"] = False
    return live


def parse(record: Any) -> dict | None:
    """Return the popular-times payload for one place, or None when absent."""
    container = find_container(record)
    if container is None:
        return None

    days: list[dict] = []
    all_hours: list[int] = []
    for group in container:
        day_number = group[0]
        hours_raw = group[1]
        hours: list[dict] = []
        if isinstance(hours_raw, list):
            for entry in hours_raw:
                percent = entry[1]
                hours.append({
                    "hour": entry[0],
                    "occupancyPercent": percent,
                    "label": entry[2] or None,
                    "displayHour": entry[4],
                })
                all_hours.append(percent)
        days.append({
            "day": DAY_NAMES.get(day_number, str(day_number)),
            "dayNumber": day_number,
            "hasData": bool(hours),
            "hours": hours,
            "peakOccupancyPercent": max((h["occupancyPercent"] for h in hours), default=None),
            "peakHour": max(hours, key=lambda h: h["occupancyPercent"])["hour"] if hours else None,
        })

    days.sort(key=lambda d: d["dayNumber"])
    parent = _find_parent(record, container)
    live = _parse_live(parent)

    busiest = max((d for d in days if d["hasData"]),
                  key=lambda d: d["peakOccupancyPercent"], default=None)
    covered = [d for d in days if d["hasData"]]

    return {
        "popularTimes": days,
        "daysWithData": len(covered),
        "busiestDay": busiest["day"] if busiest else None,
        "busiestHour": busiest["peakHour"] if busiest else None,
        "peakOccupancyPercent": busiest["peakOccupancyPercent"] if busiest else None,
        "averageOccupancyPercent": (
            round(sum(all_hours) / len(all_hours), 2) if all_hours else None
        ),
        **live,
    }


def to_long_rows(lead: dict, popular: dict) -> list[dict]:
    """Flatten one place into one row per day/hour.

    Wide records are unusable in a spreadsheet or a dataframe for this kind of
    analysis -- an urban planner wants to group by hour across places, which
    needs the long form.
    """
    rows = []
    for day in popular["popularTimes"]:
        for hour in day["hours"]:
            rows.append({
                "name": lead.get("name"),
                "placeId": lead.get("placeId"),
                "featureId": lead.get("featureId"),
                "primaryCategory": lead.get("primaryCategory"),
                "address": lead.get("address"),
                "latitude": lead.get("latitude"),
                "longitude": lead.get("longitude"),
                "timezone": lead.get("timezone"),
                "day": day["day"],
                "dayNumber": day["dayNumber"],
                "hour": hour["hour"],
                "displayHour": hour["displayHour"],
                "occupancyPercent": hour["occupancyPercent"],
                "label": hour["label"],
                "isPeakHour": hour["hour"] == day["peakHour"],
            })
    return rows
