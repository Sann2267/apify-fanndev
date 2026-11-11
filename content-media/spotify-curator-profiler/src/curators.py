"""Profile the people behind Spotify playlists, and what their taste looks like.

Spotify's own user-profile endpoints are closed to anonymous clients: the
profile service answers ``403 RBAC: access denied`` even with a valid
client-token, and a user page renders nothing but a display name without a
login. So a curator cannot be looked up directly by id.

What *is* open is the other direction. Every playlist names its owner in full,
and playlist search is unrestricted, so a curator can be profiled from their
work: find the playlists, read who owns them, group by owner, and describe the
taste from the tracks they actually chose. That is what this module does.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from src.entities import as_int, dig, pick_image, plain_text
from src.uris import id_from_uri, url_from_uri

# Playlists owned by this account are Spotify's own editorial output, not a
# person's. They are kept but flagged, because "Spotify" topping a curator
# ranking is true and useless.
EDITORIAL_OWNER = "spotify"


def parse_owner(node: Any) -> dict:
    data = dig(node, "data") or {}
    uri = data.get("uri")
    identifier = data.get("username") or id_from_uri(uri)
    return {
        "ownerName": data.get("name"),
        "ownerId": identifier,
        "ownerUri": uri,
        "ownerUrl": url_from_uri(uri),
        "ownerAvatar": pick_image(data.get("avatar")),
        "ownerSocialHandle": data.get("socialHandle"),
        "isEditorial": (identifier or "").lower() == EDITORIAL_OWNER,
    }


def parse_search_playlist(data: dict) -> dict | None:
    """A playlist as it appears in search results -- no follower count yet."""
    uri = data.get("uri")
    if not uri:
        return None
    return {
        "playlistName": data.get("name"),
        "playlistId": id_from_uri(uri),
        "playlistUri": uri,
        "playlistUrl": url_from_uri(uri),
        "description": plain_text(data.get("description")),
        "coverArt": pick_image(data.get("images")),
        **parse_owner(data.get("ownerV2")),
    }


def profile_tracks(tracks: list[dict]) -> dict:
    """Describe a set of tracks: who is on it, how mainstream, how old.

    These are the numbers that make one curator comparable to another. Play
    count is used as the popularity measure because it is an absolute figure
    Spotify publishes here and nowhere in its official API -- a curator whose
    median track has 2 000 plays is doing something very different from one
    whose median track has 200 million.
    """
    if not tracks:
        return {"trackSample": 0}

    artists: Counter = Counter()
    for track in tracks:
        for name in track.get("artistNames") or []:
            artists[name] += 1

    playcounts = [t["playcount"] for t in tracks if isinstance(t.get("playcount"), int)]
    years = [
        int(t["releaseDate"][:4])
        for t in tracks
        if isinstance(t.get("releaseDate"), str) and t["releaseDate"][:4].isdigit()
    ]
    explicit = sum(1 for t in tracks if t.get("explicit"))

    profile: dict[str, Any] = {
        "trackSample": len(tracks),
        "distinctArtists": len(artists),
        "topArtists": [
            {"artistName": name, "trackCount": count} for name, count in artists.most_common(10)
        ],
        "topArtistNames": [name for name, _ in artists.most_common(10)],
        "explicitShare": round(explicit / len(tracks), 3),
    }
    if playcounts:
        profile["medianPlaycount"] = int(median(playcounts))
        profile["maxPlaycount"] = max(playcounts)
        # A low median with a high maximum is the signature of a discovery
        # curator: mostly unknown tracks with one or two anchors.
        profile["undergroundScore"] = round(
            1 - min(1.0, profile["medianPlaycount"] / 50_000_000), 3
        )
    if years:
        profile["medianReleaseYear"] = int(median(years))
        profile["oldestReleaseYear"] = min(years)
        profile["newestReleaseYear"] = max(years)
        profile["catalogueSpreadYears"] = max(years) - min(years)
    return profile


def summarise_owner(owner: dict, playlists: list[dict], tracks: list[dict]) -> dict:
    """One row per curator, aggregating everything found under their name."""
    followers = [p["followers"] for p in playlists if isinstance(p.get("followers"), int)]
    sizes = [p["trackCount"] for p in playlists if isinstance(p.get("trackCount"), int)]
    biggest = max(
        (p for p in playlists if isinstance(p.get("followers"), int)),
        key=lambda p: p["followers"],
        default=None,
    )
    updated = [p.get("lastUpdated") for p in playlists if p.get("lastUpdated")]

    record = {
        **owner,
        "playlistsFound": len(playlists),
        "totalFollowers": sum(followers) if followers else None,
        "maxPlaylistFollowers": max(followers) if followers else None,
        "totalTracksCurated": sum(sizes) if sizes else None,
        "biggestPlaylistName": biggest.get("playlistName") if biggest else None,
        "biggestPlaylistUrl": biggest.get("playlistUrl") if biggest else None,
        "playlistNames": [p.get("playlistName") for p in playlists if p.get("playlistName")],
        "playlistUrls": [p.get("playlistUrl") for p in playlists if p.get("playlistUrl")],
        "lastUpdated": max(updated) if updated else None,
        **profile_tracks(tracks),
    }
    # A single reach figure makes curators sortable, which is the whole point
    # of the row. Followers are per playlist, so they are summed rather than
    # taken from the biggest one.
    record["reach"] = record.get("totalFollowers") or 0
    return record


def merge_owner_keys(record: dict) -> str:
    """Group key for a curator: the stable user id, falling back to the name."""
    return (record.get("ownerId") or record.get("ownerName") or "unknown").lower()
