"""Read a Spotify playlist and its tracks through the web player's GraphQL API.

``fetchPlaylist`` returns the playlist header and a page of its contents in one
request. The page size Spotify honours is not the one you ask for: the
``pagingInfo`` block echoes whatever limit was sent, but the server caps the
number of items it actually returns, so paging is driven by counting the items
that came back rather than by trusting the echo.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.constants import REQUEST_DELAY
from src.entities import artist_refs, dig, iso_date, parse_track, pick_image, plain_text
from src.spotify import SpotifyClient, UnexpectedShape
from src.uris import id_from_uri, url_from_uri

# Spotify refuses to serve more than this in one fetchPlaylist call regardless of
# the limit requested, so ask for exactly this much and page on the item count.
PAGE_SIZE = 100


def parse_owner(node: Any) -> dict:
    """``ownerV2`` -> a flat owner record.

    Editorial playlists are owned by the ``spotify`` account; everything else is
    a real user, and ``username`` is the id that appears in profile links while
    ``name`` is the display name they chose.
    """
    data = dig(node, "data") or {}
    uri = data.get("uri")
    return {
        "ownerName": data.get("name"),
        "ownerId": data.get("username") or id_from_uri(uri),
        "ownerUri": uri,
        "ownerUrl": url_from_uri(uri),
        "ownerAvatar": pick_image(data.get("avatar")),
        "ownerSocialHandle": data.get("socialHandle"),
    }


def parse_header(playlist: dict) -> dict:
    """The playlist itself, without its tracks."""
    uri = playlist.get("uri")
    attributes = {
        entry.get("key"): entry.get("value")
        for entry in (playlist.get("attributes") or [])
        if isinstance(entry, dict) and entry.get("key")
    }
    record = {
        "playlistName": playlist.get("name"),
        "playlistId": id_from_uri(uri),
        "playlistUri": uri,
        "playlistUrl": url_from_uri(uri),
        "description": plain_text(playlist.get("description")),
        "followers": playlist.get("followers"),
        "trackCount": dig(playlist, "content", "totalCount"),
        "coverArt": pick_image(playlist.get("images")),
        "shareUrl": dig(playlist, "sharingInfo", "shareUrl"),
        "collaborative": bool(playlist.get("collaborative")),
        **parse_owner(playlist.get("ownerV2")),
    }
    # Editorial charts hang their freshness and ranking basis off the playlist as
    # loose key/value attributes; ordinary playlists have none of them.
    if attributes:
        record["lastUpdated"] = attributes.get("last_updated")
        record["rankType"] = attributes.get("rank_type")
        record["chartEntityType"] = attributes.get("chart_entity_type")
        new_entries = attributes.get("new_entries_count")
        record["newEntriesCount"] = int(new_entries) if str(new_entries).isdigit() else None
        record["isEditorialChart"] = bool(attributes.get("rank_type"))
    else:
        record["isEditorialChart"] = False
    return record


def parse_items(playlist: dict, start_position: int) -> list[dict]:
    """Track rows from one page of playlist contents.

    A playlist can hold episodes and local files alongside tracks; anything that
    is not a real Spotify track is skipped rather than emitted as a row of
    nulls, and the position counter still advances so positions stay truthful.
    """
    items = dig(playlist, "content", "items", default=[])
    if not isinstance(items, list):
        raise UnexpectedShape("fetchPlaylist no longer returns content.items as a list.")
    rows = []
    for offset, item in enumerate(items):
        position = start_position + offset + 1
        wrapper = (item or {}).get("itemV2") or {}
        data = wrapper.get("data") or {}
        if wrapper.get("__typename") != "TrackResponseWrapper" or not data.get("uri"):
            continue
        row = parse_track(data)
        row["position"] = position
        row["addedAt"] = iso_date(dig(item, "addedAt"))
        row["addedById"] = id_from_uri(dig(item, "addedBy", "data", "uri"))
        rows.append(row)
    return rows


async def fetch_playlist(
    client: SpotifyClient,
    playlist_id: str,
    max_tracks: int,
    log: Any = None,
) -> tuple[dict, list[dict]]:
    """Return ``(header, tracks)`` for one playlist, paging until satisfied."""
    header: dict | None = None
    tracks: list[dict] = []
    offset = 0

    while True:
        payload = await client.entity(
            "fetchPlaylist",
            {
                "uri": f"spotify:playlist:{playlist_id}",
                "offset": offset,
                "limit": PAGE_SIZE,
                "enableWatchFeedEntrypoint": False,
            },
            "playlistV2",
        )
        if header is None:
            header = parse_header(payload)
        page = parse_items(payload, offset)
        raw_count = len(dig(payload, "content", "items", default=[]) or [])
        tracks.extend(page)

        total = header.get("trackCount") or 0
        offset += raw_count
        if log and total > PAGE_SIZE:
            log.info(f"  {min(offset, total)}/{total} items read")

        if raw_count == 0 or offset >= total or len(tracks) >= max_tracks:
            break
        await asyncio.sleep(REQUEST_DELAY)

    if header is None:  # unreachable in practice; keeps the contract explicit
        raise UnexpectedShape("fetchPlaylist returned no playlist header.")
    return header, tracks[:max_tracks]


def parse_standalone_track(track: dict) -> dict:
    """``getTrack`` -> the same row shape a playlist track produces.

    ``getTrack`` names the artists differently from the playlist query --
    ``firstArtist``/``otherArtists`` instead of one ``artists`` list -- so they
    are merged here rather than in the shared parser.
    """
    merged = dict(track)
    first = artist_refs(dig(track, "firstArtist", "items")) or []
    others = artist_refs(dig(track, "otherArtists", "items")) or []
    combined = first + others
    merged["artists"] = {"items": [
        {"uri": a["uri"], "profile": {"name": a["name"]}} for a in combined
    ]}
    row = parse_track(merged)
    album = track.get("albumOfTrack") or {}
    row["label"] = next(
        (
            entry.get("text")
            for entry in dig(album, "copyright", "items", default=[]) or []
            if isinstance(entry, dict) and entry.get("type") == "P"
        ),
        None,
    )
    row["copyright"] = [
        entry.get("text")
        for entry in dig(album, "copyright", "items", default=[]) or []
        if isinstance(entry, dict) and entry.get("text")
    ]
    row["shareUrl"] = dig(track, "sharingInfo", "shareUrl")
    return row
