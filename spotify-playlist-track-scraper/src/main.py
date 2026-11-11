"""Spotify Playlist & Track Metadata Scraper -- Apify actor entry point."""

from __future__ import annotations

import asyncio
from typing import Any

from apify import Actor

from src import exporters
from src.constants import REQUEST_DELAY
from src.enrich import Enricher
from src.entities import envelope, error_record
from src.playlists import fetch_playlist, parse_standalone_track
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.spotify import NotFound, SpotifyClient, SpotifyError, UnexpectedShape
from src.uris import BadReference, parse_reference, url_of
from src.input_errors import input_error

SOURCE_PLAYLIST = "pathfinder-fetchPlaylist"
SOURCE_TRACK = "pathfinder-getTrack"

COLUMNS = [
    "position", "trackName", "artistName", "albumName", "releaseDate", "duration",
    "playcount", "popularity", "isrc", "explicit", "durationMs", "trackId",
    "trackUrl", "albumUrl", "coverArt", "previewUrl", "addedAt",
    "playlistName", "playlistUrl", "ownerName", "recordType",
]


async def handle_playlist(
    client: SpotifyClient,
    reference: str,
    playlist_id: str,
    max_tracks: int,
    include_header: bool,
) -> tuple[list[dict], list[dict]]:
    """Return ``(dataset rows, track rows)`` for one playlist."""
    header, tracks = await fetch_playlist(client, playlist_id, max_tracks, log=Actor.log)
    followers = header.get("followers")
    summary = f"{len(tracks)} track(s) of {header.get('trackCount')}"
    if isinstance(followers, int):
        summary += f", {followers:,} followers"
    Actor.log.info(f"  {header.get('playlistName')!r}: {summary}")

    context = {
        "playlistName": header.get("playlistName"),
        "playlistId": header.get("playlistId"),
        "playlistUrl": header.get("playlistUrl"),
        "ownerName": header.get("ownerName"),
        "ownerId": header.get("ownerId"),
    }
    for row in tracks:
        row.update(context)

    rows: list[dict] = []
    if include_header:
        rows.append(envelope(reference, SOURCE_PLAYLIST, "PLAYLIST", header))
    return rows, tracks


async def handle_track(client: SpotifyClient, reference: str, track_id: str) -> dict:
    payload = await client.entity(
        "getTrack", {"uri": f"spotify:track:{track_id}"}, "trackUnion"
    )
    return parse_standalone_track(payload)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        references = dedupe(
            string_list(actor_input.get("playlistUrls"))
            + string_list(actor_input.get("trackUrls"))
            + string_list(actor_input.get("startUrls"))
        )
        if not references:
            raise input_error(
                "Nothing to do. Supply playlistUrls (for example "
                "https://open.spotify.com/playlist/37i9dQZEVXbMDoHDwVN2tF) and/or "
                "trackUrls. Share links, spotify: URIs and bare ids all work."
            )

        max_tracks = clamp(actor_input.get("maxTracksPerPlaylist", 1000), 1, 10000, 1000)
        include_header = bool(actor_input.get("includePlaylistRecord", True))
        enrich_isrc = bool(actor_input.get("enrichWithIsrc"))
        enrich_budget = clamp(actor_input.get("maxIsrcLookups", 200), 0, 5000, 200)
        market = (actor_input.get("market") or "US").upper()
        export_formats = actor_input.get("exportFormats") or []

        exporters.configure(
            preferred=COLUMNS,
            skip={"artists", "copyright", "coverArtSmall"},
            sheet="Playlist tracks",
            stem="spotify-playlist-tracks",
        )

        proxy_url = await proxy_url_from(Actor, actor_input)
        all_records: list[dict] = []
        track_rows: list[dict] = []
        failures = 0

        async with SpotifyClient(
            proxy_url=proxy_url, market=market, log=Actor.log
        ) as client:
            for position, reference in enumerate(references, start=1):
                Actor.log.info(f"[{position}/{len(references)}] {reference}")
                try:
                    kind, identifier = parse_reference(reference)
                except BadReference as exc:
                    Actor.log.warning(f"  {exc}")
                    all_records.append(error_record(reference, "unparsable_input", str(exc)))
                    failures += 1
                    continue

                try:
                    if kind == "playlist":
                        rows, tracks = await handle_playlist(
                            client, reference, identifier, max_tracks, include_header
                        )
                        all_records.extend(rows)
                        track_rows.extend(tracks)
                    elif kind == "track":
                        row = await handle_track(client, reference, identifier)
                        track_rows.append(row)
                    else:
                        message = (
                            f"{url_of(kind, identifier)} is a Spotify {kind}. This actor "
                            f"reads playlists and tracks."
                        )
                        Actor.log.warning(f"  {message}")
                        all_records.append(
                            error_record(reference, "unsupported_entity", message)
                        )
                        failures += 1
                        continue
                except NotFound as exc:
                    Actor.log.warning(f"  {exc}")
                    all_records.append(error_record(reference, "not_found", str(exc)))
                    failures += 1
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  failed: {exc}")
                    all_records.append(error_record(reference, "fetch_failed", str(exc)))
                    failures += 1
                await asyncio.sleep(REQUEST_DELAY)

            if enrich_isrc and track_rows and enrich_budget:
                Actor.log.info(
                    f"Enriching up to {min(enrich_budget, len(track_rows))} track(s) with "
                    f"ISRC and popularity -- one search request each."
                )
                enricher = Enricher(client, market, log=Actor.log)
                await enricher.enrich(track_rows, enrich_budget)
                Actor.log.info(
                    f"Enriched {enricher.enriched}/{enricher.attempted} "
                    f"({enricher.exact} matched the exact recording)."
                )
            elif not enrich_isrc:
                for row in track_rows:
                    row.setdefault("isrcLookup", "disabled")

            requests_made = client.requests_made

        # Enrichment mutates the track rows, so nothing is pushed until it has
        # finished. Order the dataset the way a buyer reads it: each playlist
        # header, then every track, then anything that failed.
        headers = [r for r in all_records if r.get("recordType") == "PLAYLIST"]
        errors = [r for r in all_records if r.get("recordType") == "ERROR"]
        tracks = [
            envelope(
                row.get("playlistUrl") or row.get("trackUrl") or "",
                SOURCE_PLAYLIST if row.get("playlistId") else SOURCE_TRACK,
                "TRACK",
                row,
            )
            for row in track_rows
        ]

        ordered = headers + tracks + errors
        for record in ordered:
            await Actor.push_data(record)

        await exporters.write_exports(Actor, export_formats, ordered)

        Actor.log.info(
            f"Finished: {len(track_rows)} track(s) from {len(references) - failures} "
            f"input(s) in {requests_made} request(s) | {failures} failure(s)"
        )
        if failures and not track_rows:
            raise RuntimeError(
                "Nothing collected and every input failed -- see the ERROR records "
                "in the dataset for the reason."
            )
