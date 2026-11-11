"""Run-to-run change detection for artist metrics.

Spotify publishes monthly listeners and followers as a snapshot with no
history: today's number is all the artist page will ever tell you. The growth
question an artist manager actually has -- *is this going up, and how fast?* --
can only be answered by remembering the last reading, so each run stores one
and reports the delta against it.

The store is a **named** key-value store, not the run's own. A run-scoped store
disappears with the run, which would make every run look like the first one.
Point several scheduled runs at the same ``trackingStoreName`` and they build a
shared history; point two different watchlists at different names to keep them
apart.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SNAPSHOT_KEY = "artist-snapshot"

TRACKED_METRICS = ("monthlyListeners", "followers", "topTrackPlaycount")


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def compare(record: dict, previous: dict | None) -> dict:
    """Deltas for one artist against its previous reading."""
    if not previous:
        return {"isFirstReading": True}

    changes: dict[str, Any] = {"isFirstReading": False}
    captured = previous.get("capturedAt")
    changes["previousReadingAt"] = captured

    before = _parse_iso(captured)
    days = None
    if before:
        elapsed = (datetime.now(timezone.utc) - before).total_seconds() / 86400
        days = round(elapsed, 2) if elapsed > 0 else None
    changes["daysSincePreviousReading"] = days

    for metric in TRACKED_METRICS:
        now = record.get(metric)
        then = previous.get(metric)
        if not isinstance(now, int) or not isinstance(then, int):
            continue
        delta = now - then
        changes[f"{metric}Previous"] = then
        changes[f"{metric}Change"] = delta
        if then:
            changes[f"{metric}ChangePercent"] = round(delta * 100 / then, 2)
        # A per-day rate is what makes two readings taken a week apart
        # comparable with two taken a day apart.
        if days and days >= 0.5:
            changes[f"{metric}ChangePerDay"] = round(delta / days)

    listeners = changes.get("monthlyListenersChange")
    if isinstance(listeners, int):
        changes["trend"] = "up" if listeners > 0 else "down" if listeners < 0 else "flat"
    return changes


def build_snapshot(records: list[dict], captured_at: str) -> dict:
    """The state this run hands to the next one."""
    return {
        "capturedAt": captured_at,
        "artists": {
            record["artistId"]: {
                "capturedAt": captured_at,
                "artistName": record.get("artistName"),
                **{m: record.get(m) for m in TRACKED_METRICS},
            }
            for record in records
            if record.get("artistId")
        },
    }


def previous_for(snapshot: dict | None, artist_id: str) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    artists = snapshot.get("artists")
    if not isinstance(artists, dict):
        return None
    entry = artists.get(artist_id)
    return entry if isinstance(entry, dict) else None
