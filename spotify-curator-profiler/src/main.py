"""Spotify Curator & Playlist Owner Profiler -- Apify actor entry point."""

from __future__ import annotations

import asyncio

from apify import Actor

from src import exporters
from src.constants import REQUEST_DELAY, SEARCH_SUGGESTIONS_CAP
from src.curators import (
    merge_owner_keys,
    parse_owner,
    parse_search_playlist,
    summarise_owner,
)
from src.entities import dig, envelope, error_record, parse_track, pick_image, plain_text
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.spotify import NotFound, SpotifyClient, SpotifyError, UnexpectedShape
from src.uris import BadReference, id_from_uri, parse_reference, url_from_uri
from src.input_errors import input_error

SOURCE_SEARCH = "pathfinder-searchSuggestions"
SOURCE_PLAYLIST = "pathfinder-fetchPlaylist"

COLUMNS = [
    "ownerName", "ownerId", "playlistsFound", "totalFollowers",
    "maxPlaylistFollowers", "totalTracksCurated", "biggestPlaylistName",
    "topArtistNames", "medianPlaycount", "undergroundScore",
    "medianReleaseYear", "explicitShare", "isEditorial", "lastUpdated",
    "ownerUrl", "playlistName", "followers", "trackCount", "playlistUrl",
    "recordType",
]


async def read_playlist(client: SpotifyClient, playlist_id: str, sample: int):
    """Playlist header plus a sample of its tracks, in one request."""
    payload = await client.entity(
        "fetchPlaylist",
        {"uri": f"spotify:playlist:{playlist_id}", "offset": 0,
         "limit": max(1, min(sample, 100)), "enableWatchFeedEntrypoint": False},
        "playlistV2",
    )
    uri = payload.get("uri")
    attributes = {
        entry.get("key"): entry.get("value")
        for entry in (payload.get("attributes") or [])
        if isinstance(entry, dict) and entry.get("key")
    }
    header = {
        "playlistName": payload.get("name"),
        "playlistId": id_from_uri(uri),
        "playlistUri": uri,
        "playlistUrl": url_from_uri(uri),
        "description": plain_text(payload.get("description")),
        "followers": payload.get("followers"),
        "trackCount": dig(payload, "content", "totalCount"),
        "coverArt": pick_image(payload.get("images")),
        "lastUpdated": attributes.get("last_updated"),
        **parse_owner(payload.get("ownerV2")),
    }
    tracks = []
    for item in dig(payload, "content", "items", default=[]) or []:
        wrapper = (item or {}).get("itemV2") or {}
        if wrapper.get("__typename") != "TrackResponseWrapper":
            continue
        data = wrapper.get("data") or {}
        if data.get("uri"):
            tracks.append(parse_track(data))
    return header, tracks[:sample]


async def discover(client: SpotifyClient, keyword: str, log) -> list[dict]:
    """Playlists Spotify's own search returns for a keyword."""
    hits = await client.suggest(keyword)
    found = []
    for hit in hits:
        if hit["kind"] != "Playlist":
            continue
        record = parse_search_playlist(hit["data"])
        if record:
            record["foundVia"] = keyword
            found.append(record)
    log.info(f"  {len(found)} playlist(s) among {len(hits)} search hit(s)")
    return found


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        keywords = dedupe(string_list(actor_input.get("keywords")))
        direct = dedupe(
            string_list(actor_input.get("playlistUrls"))
            + string_list(actor_input.get("startUrls"))
        )
        if not keywords and not direct:
            raise input_error(
                "Nothing to do. Supply keywords to discover playlists by topic "
                "(for example ['indie folk', 'lofi study']), and/or playlistUrls "
                "to profile the owners of specific playlists."
            )

        sample = clamp(actor_input.get("trackSampleSize", 50), 0, 100, 50)
        max_playlists = clamp(actor_input.get("maxPlaylistsPerKeyword", 15), 1, 30, 15)
        max_total = clamp(actor_input.get("maxPlaylists", 200), 1, 2000, 200)
        include_editorial = bool(actor_input.get("includeEditorialPlaylists", False))
        min_followers = clamp(actor_input.get("minFollowers", 0), 0, 100_000_000, 0)
        emit_playlists = bool(actor_input.get("emitPlaylistRecords", True))
        export_formats = actor_input.get("exportFormats") or []

        exporters.configure(
            preferred=COLUMNS,
            skip={"topArtists", "playlistNames", "playlistUrls", "artists",
                  "description", "artistNames"},
            sheet="Curators",
            stem="spotify-curators",
        )

        proxy_url = await proxy_url_from(Actor, actor_input)
        playlist_records: list[dict] = []
        errors: list[dict] = []
        owners: dict[str, dict] = {}
        owner_playlists: dict[str, list[dict]] = {}
        owner_tracks: dict[str, list[dict]] = {}

        async with SpotifyClient(proxy_url=proxy_url, log=Actor.log) as client:
            # -- 1. discover candidate playlists ---------------------------
            candidates: list[dict] = []
            for position, keyword in enumerate(keywords, start=1):
                Actor.log.info(f"[keyword {position}/{len(keywords)}] {keyword!r}")
                try:
                    found = await discover(client, keyword, Actor.log)
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  search failed: {exc}")
                    errors.append(error_record(keyword, "search_failed", str(exc)))
                    continue
                candidates.extend(found[:max_playlists])
                await asyncio.sleep(REQUEST_DELAY)

            for reference in direct:
                try:
                    kind, identifier = parse_reference(reference, default_kind="playlist")
                    if kind != "playlist":
                        raise BadReference(f"{reference!r} is a Spotify {kind}, not a playlist.")
                except BadReference as exc:
                    Actor.log.warning(f"  {exc}")
                    errors.append(error_record(reference, "unparsable_input", str(exc)))
                    continue
                candidates.append(
                    {"playlistId": identifier, "playlistUrl": reference, "foundVia": "input"}
                )

            # De-duplicate: one playlist can surface under several keywords.
            unique: dict[str, dict] = {}
            for candidate in candidates:
                key = candidate.get("playlistId")
                if key and key not in unique:
                    unique[key] = candidate
            targets = list(unique.values())[:max_total]
            Actor.log.info(
                f"{len(targets)} distinct playlist(s) to profile "
                f"(from {len(candidates)} hit(s))."
            )

            # -- 2. read each playlist for followers, owner and tracks -----
            for position, candidate in enumerate(targets, start=1):
                try:
                    header, tracks = await read_playlist(
                        client, candidate["playlistId"], sample
                    )
                except NotFound as exc:
                    errors.append(
                        error_record(candidate.get("playlistUrl") or "", "not_found", str(exc))
                    )
                    continue
                except (SpotifyError, UnexpectedShape) as exc:
                    errors.append(
                        error_record(candidate.get("playlistUrl") or "", "fetch_failed", str(exc))
                    )
                    continue

                header["foundVia"] = candidate.get("foundVia")
                if header.get("isEditorial") and not include_editorial:
                    continue
                if min_followers and (header.get("followers") or 0) < min_followers:
                    continue

                key = merge_owner_keys(header)
                owners.setdefault(key, {k: header[k] for k in (
                    "ownerName", "ownerId", "ownerUri", "ownerUrl",
                    "ownerAvatar", "ownerSocialHandle", "isEditorial")})
                owner_playlists.setdefault(key, []).append(header)
                owner_tracks.setdefault(key, []).extend(tracks)
                playlist_records.append(header)

                if position % 10 == 0 or position == len(targets):
                    Actor.log.info(
                        f"  {position}/{len(targets)} playlists read, "
                        f"{len(owners)} curator(s) so far"
                    )
                await asyncio.sleep(REQUEST_DELAY)

            requests_made = client.requests_made

        # -- 3. one row per curator ----------------------------------------
        curator_rows = [
            summarise_owner(owner, owner_playlists.get(key, []), owner_tracks.get(key, []))
            for key, owner in owners.items()
        ]
        curator_rows.sort(key=lambda row: row.get("reach") or 0, reverse=True)

        ordered = (
            [envelope(r.get("ownerUrl") or "", SOURCE_SEARCH, "CURATOR", r) for r in curator_rows]
            + (
                [
                    envelope(r.get("playlistUrl") or "", SOURCE_PLAYLIST, "PLAYLIST", r)
                    for r in playlist_records
                ]
                if emit_playlists
                else []
            )
            + errors
        )
        for record in ordered:
            await Actor.push_data(record)
        await exporters.write_exports(Actor, export_formats, ordered)

        top = curator_rows[0] if curator_rows else None
        Actor.log.info(
            f"Finished: {len(curator_rows)} curator(s) across {len(playlist_records)} "
            f"playlist(s) in {requests_made} request(s) | {len(errors)} failure(s)"
        )
        if top:
            Actor.log.info(
                f"Biggest reach: {top.get('ownerName')} -- "
                f"{top.get('playlistsFound')} playlist(s), "
                f"{top.get('totalFollowers') or 0:,} follower(s)"
            )
        if keywords and len(playlist_records) < 3:
            Actor.log.info(
                f"Few playlists found. Spotify's search returns at most "
                f"{SEARCH_SUGGESTIONS_CAP} mixed results per keyword and ignores "
                f"paging, so breadth comes from using more keywords rather than "
                f"from asking for more results per keyword."
            )
        if errors and not curator_rows:
            raise RuntimeError(
                "No curators profiled and every input failed -- see the ERROR "
                "records in the dataset for the reason."
            )
