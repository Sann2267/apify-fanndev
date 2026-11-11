"""Parse Spotify's artist overview into an analytics record.

``queryArtistOverview`` returns roughly 110 KB per artist and carries every
public number Spotify shows on an artist page: monthly listeners, followers,
the five cities with the most listeners, the ten most-played tracks with their
lifetime play counts, the discography totals, the playlists the artist is being
discovered on, upcoming concerts, and the artist's own social links.

One request per artist. Everything below is a read of that single payload.
"""

from __future__ import annotations

from typing import Any

from src.entities import (
    artist_refs,
    as_int,
    dig,
    iso_date,
    ms_to_clock,
    pick_image,
    plain_text,
    real_items,
)
from src.uris import id_from_uri, url_from_uri

# Spotify names its external links by platform in a fixed vocabulary.
SOCIAL_KEYS = {
    "FACEBOOK": "facebook",
    "INSTAGRAM": "instagram",
    "TWITTER": "twitter",
    "TIKTOK": "tiktok",
    "WIKIPEDIA": "wikipedia",
    "YOUTUBE": "youtube",
}


def parse_stats(artist: dict) -> dict:
    """Follower and listener numbers, plus the top-cities breakdown."""
    stats = artist.get("stats") or {}
    cities = []
    for entry in dig(stats, "topCities", "items", default=[]) or []:
        if not isinstance(entry, dict):
            continue
        cities.append(
            {
                "city": entry.get("city"),
                "country": entry.get("country"),
                "region": entry.get("region"),
                "listeners": as_int(entry.get("numberOfListeners")),
            }
        )
    monthly = as_int(stats.get("monthlyListeners"))
    followers = as_int(stats.get("followers"))
    record: dict[str, Any] = {
        "monthlyListeners": monthly,
        "followers": followers,
        "topCities": cities,
        "topCityNames": [c["city"] for c in cities if c.get("city")],
        "listenersInTopCities": sum(c["listeners"] or 0 for c in cities) or None,
    }
    # worldRank is 0 for every artist outside Spotify's published global ranking,
    # which is the overwhelming majority. Emitting 0 would read as "ranked first".
    rank = as_int(stats.get("worldRank"))
    record["worldRank"] = rank if rank else None
    # A ratio between the two headline numbers is the metric managers actually
    # watch: listeners who have not converted into followers are the growth gap.
    if monthly and followers:
        record["listenersPerFollower"] = round(monthly / followers, 2)
    return record


def parse_profile(artist: dict) -> dict:
    profile = artist.get("profile") or {}
    links = {}
    for entry in dig(profile, "externalLinks", "items", default=[]) or []:
        if not isinstance(entry, dict):
            continue
        key = SOCIAL_KEYS.get(str(entry.get("name", "")).upper())
        if key and entry.get("url"):
            links[key] = entry["url"]
    uri = artist.get("uri")
    return {
        "artistName": profile.get("name"),
        "artistId": artist.get("id") or id_from_uri(uri),
        "artistUri": uri,
        "artistUrl": url_from_uri(uri),
        "biography": plain_text(dig(profile, "biography", "text")),
        "socialLinks": links,
        "avatarImage": pick_image(dig(artist, "visuals", "avatarImage")),
        "headerImage": pick_image(dig(artist, "headerImage", "data")),
        "shareUrl": dig(artist, "sharingInfo", "shareUrl"),
        "verified": dig(artist, "profile", "verified"),
    }


def parse_top_tracks(artist: dict) -> list[dict]:
    """The ten tracks Spotify shows as most played, with lifetime play counts."""
    rows = []
    items = dig(artist, "discography", "topTracks", "items", default=[]) or []
    for position, entry in enumerate(items, start=1):
        track = (entry or {}).get("track") or {}
        uri = track.get("uri")
        if not uri:
            continue
        duration = dig(track, "duration", "totalMilliseconds")
        rows.append(
            {
                "rank": position,
                "trackName": track.get("name"),
                "trackId": track.get("id") or id_from_uri(uri),
                "trackUri": uri,
                "trackUrl": url_from_uri(uri),
                "playcount": as_int(track.get("playcount")),
                "durationMs": duration,
                "duration": ms_to_clock(duration),
                "explicit": dig(track, "contentRating", "label") == "EXPLICIT",
                "albumUri": dig(track, "albumOfTrack", "uri"),
                "coverArt": pick_image(dig(track, "albumOfTrack", "coverArt")),
                "featuredArtists": [
                    a["name"]
                    for a in artist_refs(track.get("artists"))
                    if a.get("uri") != artist.get("uri")
                ],
            }
        )
    return rows


def _release(entry: dict) -> dict | None:
    """Discography entries wrap the real release one level down.

    Each item is ``{"releases": {"items": [ <the album> ]}}`` -- reading the
    item itself yields nothing, which is why a naive parse returns empty
    discographies.
    """
    releases = dig(entry, "releases", "items", default=[]) or []
    return releases[0] if releases and isinstance(releases[0], dict) else None


def parse_discography(artist: dict) -> dict:
    discography = artist.get("discography") or {}
    summary = {
        "albumCount": dig(discography, "albums", "totalCount"),
        "singleCount": dig(discography, "singles", "totalCount"),
        "compilationCount": dig(discography, "compilations", "totalCount"),
    }
    latest = None
    newest_date = ""
    for group in ("albums", "singles", "compilations"):
        for entry in dig(discography, group, "items", default=[]) or []:
            release = _release(entry)
            if not release:
                continue
            date = iso_date(release.get("date")) or ""
            if date > newest_date:
                newest_date = date
                latest = {
                    "latestReleaseName": release.get("name"),
                    "latestReleaseDate": date,
                    "latestReleaseType": group[:-1],
                    "latestReleaseUrl": url_from_uri(release.get("uri")),
                }
    summary.update(latest or {})
    return summary


def parse_discovery(artist: dict) -> dict:
    """Playlists the artist is being discovered on, and who they sit next to.

    ``discoveredOnV2`` is the single most actionable list on the page for an
    artist team: it names the playlists actually feeding the artist listeners.
    Spotify pads it with placeholder entries, which are dropped here.
    """
    related = artist.get("relatedContent") or {}

    def playlists(key: str) -> list[dict]:
        return [
            {
                "playlistName": item.get("name"),
                "playlistId": item.get("id") or id_from_uri(item.get("uri")),
                "playlistUrl": url_from_uri(item.get("uri")),
                "description": plain_text(item.get("description")),
                "coverArt": pick_image(item.get("images")),
                "ownerName": dig(item, "ownerV2", "data", "name"),
            }
            for item in real_items(related.get(key))
            if item.get("uri")
        ]

    # relatedArtists items are bare artist objects, not wrapped in a "data" key
    # the way playlist lists are -- Spotify is inconsistent about this within a
    # single payload, so the two lists are read differently on purpose.
    peers = [
        {
            "artistName": dig(item, "profile", "name"),
            "artistId": item.get("id") or id_from_uri(item.get("uri")),
            "artistUrl": url_from_uri(item.get("uri")),
        }
        for item in (dig(related, "relatedArtists", "items", default=[]) or [])
        if isinstance(item, dict) and item.get("uri")
    ]

    discovered = playlists("discoveredOnV2")
    featured = playlists("featuringV2")
    return {
        "discoveredOnPlaylists": discovered,
        "discoveredOnCount": len(discovered),
        "featuredInPlaylists": featured,
        "relatedArtists": peers,
        "relatedArtistNames": [p["artistName"] for p in peers if p.get("artistName")],
    }


def parse_concerts(artist: dict) -> list[dict]:
    """Upcoming dates Spotify lists for the artist."""
    rows = []
    for concert in real_items(dig(artist, "goods", "concerts")):
        rows.append(
            {
                "title": concert.get("title"),
                "startsAt": concert.get("startDateIsoString"),
                "city": dig(concert, "location", "city"),
                "venue": dig(concert, "location", "name"),
                "isFestival": bool(concert.get("festival")),
                "concertUrl": url_from_uri(concert.get("uri")),
            }
        )
    return rows


def parse_artist(artist: dict, include: dict) -> tuple[dict, list[dict]]:
    """Return ``(artist record, top track rows)``."""
    record: dict[str, Any] = {}
    record.update(parse_profile(artist))
    record.update(parse_stats(artist))
    record.update(parse_discography(artist))

    top_tracks = parse_top_tracks(artist)
    if top_tracks:
        record["topTrackName"] = top_tracks[0]["trackName"]
        record["topTrackPlaycount"] = top_tracks[0]["playcount"]
        record["topTracksTotalPlaycount"] = sum(
            row["playcount"] or 0 for row in top_tracks
        ) or None

    if include.get("discovery"):
        record.update(parse_discovery(artist))
    if include.get("concerts"):
        concerts = parse_concerts(artist)
        record["upcomingConcerts"] = concerts
        record["upcomingConcertCount"] = len(concerts)
    if include.get("topTracks"):
        record["topTracks"] = top_tracks
    return record, top_tracks
