"""Read Spotify charts from the two surfaces that publish them.

**Editorial chart playlists** (``Top 50 - <country>``, ``Top Songs - <country>``)
come from the same GraphQL query as any other playlist, and carry the ranking
in track order plus a small ``attributes`` block giving the recalculation time,
what the ranking counts, and how many entries are new. They cover roughly fifty
territories, but they publish only *today's* order -- no previous position.

**The public charts service** needs no token at all and answers with real chart
records including ``previousRank`` and ``entryStatus``, for tracks, albums *and*
artists. It serves only the three global weekly charts; everything per-country
or historical sits behind an authenticated path.

Rank movement for the playlist-based charts is therefore computed locally, by
remembering the previous run's order.
"""

from __future__ import annotations

from typing import Any

from src.constants import CHARTS_PUBLIC_URL
from src.entities import as_int, dig, pick_image, plain_text
from src.spotify import SpotifyClient
from src.uris import id_from_uri, url_from_uri


def chart_attributes(playlist: dict) -> dict:
    attributes = {
        entry.get("key"): entry.get("value")
        for entry in (playlist.get("attributes") or [])
        if isinstance(entry, dict) and entry.get("key")
    }
    new_entries = attributes.get("new_entries_count")
    return {
        "chartLastUpdated": attributes.get("last_updated"),
        "rankType": attributes.get("rank_type"),
        "chartEntityType": attributes.get("chart_entity_type"),
        "newEntriesReported": int(new_entries) if str(new_entries).isdigit() else None,
    }


def parse_chart_header(playlist: dict, country: str, recurrence: str) -> dict:
    uri = playlist.get("uri")
    return {
        "chartName": playlist.get("name"),
        "country": country,
        "recurrence": recurrence,
        "chartId": id_from_uri(uri),
        "chartUrl": url_from_uri(uri),
        "description": plain_text(playlist.get("description")),
        "followers": playlist.get("followers"),
        "entryCount": dig(playlist, "content", "totalCount"),
        "coverArt": pick_image(playlist.get("images")),
        **chart_attributes(playlist),
    }


def parse_chart_entries(playlist: dict) -> list[dict]:
    """Chart rows in rank order. Rank *is* the playlist position."""
    rows = []
    rank = 0
    for item in dig(playlist, "content", "items", default=[]) or []:
        wrapper = (item or {}).get("itemV2") or {}
        data = wrapper.get("data") or {}
        uri = data.get("uri")
        if wrapper.get("__typename") != "TrackResponseWrapper" or not uri:
            continue
        rank += 1
        artists = [
            {"name": dig(a, "profile", "name"), "uri": a.get("uri")}
            for a in dig(data, "artists", "items", default=[]) or []
            if isinstance(a, dict)
        ]
        album = data.get("albumOfTrack") or {}
        rows.append(
            {
                "rank": rank,
                "trackName": data.get("name"),
                "artistName": artists[0]["name"] if artists else None,
                "artistNames": [a["name"] for a in artists if a.get("name")],
                "artistId": id_from_uri(artists[0]["uri"]) if artists else None,
                "artistUrl": url_from_uri(artists[0]["uri"]) if artists else None,
                "trackId": id_from_uri(uri),
                "trackUri": uri,
                "trackUrl": url_from_uri(uri),
                "albumName": album.get("name"),
                "albumUrl": url_from_uri(album.get("uri")),
                "playcount": as_int(data.get("playcount")),
                "durationMs": dig(data, "trackDuration", "totalMilliseconds"),
                "explicit": dig(data, "contentRating", "label") == "EXPLICIT",
                "coverArt": pick_image(album.get("coverArt")),
            }
        )
    return rows


# -- the public, tokenless charts service ---------------------------------

ENTITY_KEYS = {
    "trackMetadata": ("TRACK", "trackName", "trackUri"),
    "albumMetadata": ("ALBUM", "albumName", "albumUri"),
    "artistMetadata": ("ARTIST", "artistName", "artistUri"),
}


def _entity_fields(entry: dict) -> dict:
    """Normalise whichever of the three metadata shapes this entry carries."""
    for key, (kind, name_field, uri_field) in ENTITY_KEYS.items():
        metadata = entry.get(key)
        if not isinstance(metadata, dict):
            continue
        uri = metadata.get(uri_field)
        artists = [
            {"name": a.get("name"), "uri": a.get("spotifyUri")}
            for a in (metadata.get("artists") or [])
            if isinstance(a, dict) and a.get("name")
        ]
        # The service sends "" rather than null for credits it has not filled
        # in -- labels, songwriters, producers and releaseDate are empty far
        # more often than not -- so empties are dropped instead of emitted.
        optional = {
            "entityId": id_from_uri(uri),
            "entityUri": uri,
            "entityUrl": url_from_uri(uri),
            "coverArt": metadata.get("displayImageUri"),
            "artistNames": [a["name"] for a in artists],
            "artistName": artists[0]["name"] if artists else None,
            "labels": metadata.get("labels"),
            "songwriters": metadata.get("songWriters"),
            "producers": metadata.get("producers"),
            "releaseDate": metadata.get("releaseDate"),
        }
        fields = {"entityType": kind, "entityName": metadata.get(name_field)}
        fields.update({k: v for k, v in optional.items() if v not in ([], None, "")})
        return fields
    return {}


def parse_public_entry(entry: dict) -> dict | None:
    data = entry.get("chartEntryData") or {}
    fields = _entity_fields(entry)
    if not fields.get("entityName"):
        return None
    rank = as_int(data.get("currentRank"))
    previous = as_int(data.get("previousRank"))
    # Spotify writes 0, not null, for "no previous position" and for every
    # counter it has not filled in. Passing those through would claim a track
    # was ranked 0th last week and had its peak at 0.
    record = {
        "rank": rank,
        "previousRank": previous or None,
        "entryStatus": data.get("entryStatus") or None,
        "peakRank": as_int(data.get("peakRank")) or None,
        "appearancesOnChart": as_int(data.get("appearancesOnChart")) or None,
        "consecutiveAppearances": as_int(data.get("consecutiveAppearancesOnChart")) or None,
        "peakDate": data.get("peakDate") or None,
        "entryDate": data.get("entryDate") or None,
        **fields,
    }
    if rank and previous:
        record["rankChange"] = previous - rank
    return record


async def fetch_public_charts(client: SpotifyClient) -> list[dict]:
    """The three global weekly charts, fetched without any credential."""
    payload = await client.get_json(CHARTS_PUBLIC_URL)
    views = (payload or {}).get("chartEntryViewResponses")
    if not isinstance(views, list):
        return []
    charts = []
    for view in views:
        metadata = dig(view, "displayChart", "chartMetadata") or {}
        dimensions = metadata.get("dimensions") or {}
        entries = []
        for entry in view.get("entries") or []:
            parsed = parse_public_entry(entry) if isinstance(entry, dict) else None
            if parsed:
                entries.append(parsed)
        charts.append(
            {
                "header": {
                    "chartName": metadata.get("readableTitle"),
                    "chartAlias": metadata.get("alias"),
                    "chartDate": dig(view, "displayChart", "date"),
                    "country": dimensions.get("country") or "GLOBAL",
                    "recurrence": str(dimensions.get("recurrence") or "").lower() or None,
                    "chartEntityType": dimensions.get("chartType"),
                    "earliestDate": dimensions.get("latestDate"),
                    "description": plain_text(dig(view, "displayChart", "description")),
                    "entryCount": len(entries),
                },
                "entries": entries,
            }
        )
    return charts


def summarise(entries: list[dict]) -> dict:
    """Headline movement numbers for one chart."""
    climbers = [e for e in entries if isinstance(e.get("rankChange"), int) and e["rankChange"] > 0]
    fallers = [e for e in entries if isinstance(e.get("rankChange"), int) and e["rankChange"] < 0]
    new = [e for e in entries if e.get("entryStatus") in ("NEW_ENTRY", "NEW")]
    biggest = max(climbers, key=lambda e: e["rankChange"], default=None)
    return {
        "entriesCompared": sum(1 for e in entries if e.get("previousRank")),
        "newEntries": len(new),
        "climbers": len(climbers),
        "fallers": len(fallers),
        "biggestClimbName": biggest.get("trackName") or biggest.get("entityName") if biggest else None,
        "biggestClimbPositions": biggest["rankChange"] if biggest else None,
        "newEntryNames": [e.get("trackName") or e.get("entityName") for e in new][:10],
    }
