"""Rank movement between runs, for the charts that do not publish it.

Spotify's chart *playlists* are just ordered track lists: position 1 is number
one, and that is all they say. Whether a track climbed, fell, is new or has
re-entered is nowhere in the payload -- the ``new_entries_count`` attribute
gives a total and no names.

So each run stores the order it saw and compares the next run against it. The
store is a **named** key-value store because a run-scoped one is deleted with
its run, which would make every run look like the first.

The public charts service already carries ``previousRank`` and ``entryStatus``
of its own, so those charts are passed through untouched rather than
second-guessed here.
"""

from __future__ import annotations

from typing import Any

SNAPSHOT_KEY = "chart-snapshot"


def snapshot_key(country: str, recurrence: str, chart_id: str) -> str:
    return f"{recurrence}:{country}:{chart_id}"


def apply_movement(entries: list[dict], previous: dict | None) -> None:
    """Add previousRank / rankChange / entryStatus to each entry, in place."""
    ranks = (previous or {}).get("ranks") or {}
    seen_before = bool(ranks)
    for entry in entries:
        uri = entry.get("trackUri")
        before = ranks.get(uri) if uri else None
        if not seen_before:
            # Nothing to compare against: say so rather than calling every
            # track a new entry, which would be indistinguishable from a real
            # 50-track turnover.
            entry["entryStatus"] = "BASELINE"
            continue
        if not isinstance(before, int):
            entry["entryStatus"] = "NEW_ENTRY"
            continue
        entry["previousRank"] = before
        change = before - entry["rank"]
        entry["rankChange"] = change
        entry["entryStatus"] = (
            "MOVED_UP" if change > 0 else "MOVED_DOWN" if change < 0 else "NO_CHANGE"
        )


def dropped_out(entries: list[dict], previous: dict | None) -> list[dict]:
    """Tracks that were on the chart last run and are not on it now."""
    ranks = (previous or {}).get("ranks") or {}
    names = (previous or {}).get("names") or {}
    current = {entry.get("trackUri") for entry in entries}
    out = []
    for uri, rank in ranks.items():
        if uri in current:
            continue
        out.append(
            {
                "trackUri": uri,
                "trackName": names.get(uri),
                "previousRank": rank,
                "entryStatus": "DROPPED_OUT",
            }
        )
    return sorted(out, key=lambda row: row["previousRank"])


def build_entry(entries: list[dict], captured_at: str) -> dict:
    return {
        "capturedAt": captured_at,
        "ranks": {e["trackUri"]: e["rank"] for e in entries if e.get("trackUri")},
        "names": {e["trackUri"]: e.get("trackName") for e in entries if e.get("trackUri")},
    }


def previous_for(snapshot: Any, key: str) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    charts = snapshot.get("charts")
    if not isinstance(charts, dict):
        return None
    entry = charts.get(key)
    return entry if isinstance(entry, dict) else None
