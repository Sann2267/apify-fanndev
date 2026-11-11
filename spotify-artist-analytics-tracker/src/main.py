"""Spotify Artist Analytics & Monthly Listeners Tracker -- Apify actor entry point."""

from __future__ import annotations

import asyncio

from apify import Actor

from src import exporters
from src.artists import parse_artist
from src.constants import REQUEST_DELAY
from src.entities import envelope, error_record, utc_now_iso
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.spotify import NotFound, SpotifyClient, SpotifyError, UnexpectedShape
from src.tracking import SNAPSHOT_KEY, build_snapshot, compare, previous_for
from src.uris import BadReference, parse_reference, url_of
from src.input_errors import input_error

SOURCE = "pathfinder-queryArtistOverview"
SOURCE_SEARCH = "pathfinder-searchSuggestions"

COLUMNS = [
    "artistName", "monthlyListeners", "followers", "monthlyListenersChange",
    "monthlyListenersChangePercent", "monthlyListenersChangePerDay", "trend",
    "followersChange", "listenersPerFollower", "worldRank", "topCityNames",
    "topTrackName", "topTrackPlaycount", "albumCount", "singleCount",
    "latestReleaseName", "latestReleaseDate", "discoveredOnCount",
    "upcomingConcertCount", "artistUrl", "recordType",
]


async def resolve_artist(client: SpotifyClient, text: str) -> tuple[str, str]:
    """Turn a plain artist name into an id by searching for it.

    Returns ``(artist_id, matched_name)``. Search runs through the GraphQL
    gateway rather than Spotify's Web API search, which rate-limits per IP.
    """
    hits = await client.suggest(text)
    for hit in hits:
        if hit["kind"] == "Artist":
            data = hit["data"]
            uri = data.get("uri") or ""
            identifier = uri.split(":")[-1]
            name = (data.get("profile") or {}).get("name")
            if identifier:
                return identifier, name or text
    raise NotFound(f"No Spotify artist matched {text!r}.")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        references = dedupe(
            string_list(actor_input.get("artistUrls"))
            + string_list(actor_input.get("artistNames"))
            + string_list(actor_input.get("startUrls"))
        )
        if not references:
            raise input_error(
                "Nothing to do. Supply artistUrls (for example "
                "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt) or "
                "artistNames (for example 'Tulus') to look up by name."
            )

        include = {
            "topTracks": bool(actor_input.get("includeTopTracks", True)),
            "discovery": bool(actor_input.get("includeDiscovery", True)),
            "concerts": bool(actor_input.get("includeConcerts", True)),
        }
        emit_track_rows = bool(actor_input.get("emitTopTrackRows"))
        track_changes = bool(actor_input.get("trackChanges", True))
        store_name = (actor_input.get("trackingStoreName") or "spotify-artist-analytics").strip()
        max_artists = clamp(actor_input.get("maxArtists", 200), 1, 2000, 200)
        export_formats = actor_input.get("exportFormats") or []

        references = references[:max_artists]
        exporters.configure(
            preferred=COLUMNS,
            skip={"topCities", "topTracks", "discoveredOnPlaylists",
                  "featuredInPlaylists", "relatedArtists", "upcomingConcerts",
                  "socialLinks", "biography"},
            sheet="Artist analytics",
            stem="spotify-artist-analytics",
        )

        snapshot = None
        store = None
        if track_changes:
            store = await Actor.open_key_value_store(name=store_name)
            snapshot = await store.get_value(SNAPSHOT_KEY)
            if snapshot:
                Actor.log.info(
                    f"Comparing against the previous reading in "
                    f"{store_name!r} (captured {snapshot.get('capturedAt')})."
                )
            else:
                Actor.log.info(
                    f"No previous reading in {store_name!r} -- this run establishes "
                    f"the baseline, and the next one will report changes."
                )

        proxy_url = await proxy_url_from(Actor, actor_input)
        artist_records: list[dict] = []
        track_records: list[dict] = []
        errors: list[dict] = []

        async with SpotifyClient(proxy_url=proxy_url, log=Actor.log) as client:
            for position, reference in enumerate(references, start=1):
                Actor.log.info(f"[{position}/{len(references)}] {reference}")
                source = SOURCE
                try:
                    try:
                        kind, identifier = parse_reference(reference)
                        if kind != "artist":
                            raise BadReference(
                                f"{url_of(kind, identifier)} is a Spotify {kind}. "
                                f"This actor reads artists."
                            )
                    except BadReference:
                        # Not a link, so treat it as a name to search for.
                        identifier, matched = await resolve_artist(client, reference)
                        source = SOURCE_SEARCH
                        Actor.log.info(f"  matched {matched!r}")

                    payload = await client.entity(
                        "queryArtistOverview",
                        {"uri": f"spotify:artist:{identifier}", "locale": "",
                         "includePrerelease": True},
                        "artistUnion",
                    )
                    record, top_tracks = parse_artist(payload, include)
                except NotFound as exc:
                    Actor.log.warning(f"  {exc}")
                    errors.append(error_record(reference, "not_found", str(exc)))
                    continue
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  failed: {exc}")
                    errors.append(error_record(reference, "fetch_failed", str(exc)))
                    continue

                if track_changes:
                    record.update(compare(record, previous_for(snapshot, record.get("artistId"))))

                listeners = record.get("monthlyListeners")
                change = record.get("monthlyListenersChange")
                line = f"  {record.get('artistName')}: "
                line += f"{listeners:,} monthly listeners" if listeners else "no listener data"
                if isinstance(change, int):
                    line += f" ({change:+,} since the last reading)"
                Actor.log.info(line)

                artist_records.append(record)
                if emit_track_rows:
                    for row in top_tracks:
                        track_records.append(
                            {
                                "artistName": record.get("artistName"),
                                "artistId": record.get("artistId"),
                                "artistUrl": record.get("artistUrl"),
                                **row,
                            }
                        )
                await asyncio.sleep(REQUEST_DELAY)

            requests_made = client.requests_made

        captured_at = utc_now_iso()
        ordered = (
            [envelope(r.get("artistUrl") or "", SOURCE, "ARTIST", r) for r in artist_records]
            + [envelope(r.get("artistUrl") or "", SOURCE, "TOP_TRACK", r) for r in track_records]
            + errors
        )
        for record in ordered:
            await Actor.push_data(record)

        if track_changes and store is not None and artist_records:
            await store.set_value(SNAPSHOT_KEY, build_snapshot(artist_records, captured_at))
            Actor.log.info(f"Saved this reading to {store_name!r} for the next run.")

        await exporters.write_exports(Actor, export_formats, ordered)

        rising = sum(1 for r in artist_records if r.get("trend") == "up")
        falling = sum(1 for r in artist_records if r.get("trend") == "down")
        Actor.log.info(
            f"Finished: {len(artist_records)} artist(s) in {requests_made} request(s) | "
            f"{rising} rising, {falling} falling | {len(errors)} failure(s)"
        )
        if errors and not artist_records:
            raise RuntimeError(
                "Nothing collected and every input failed -- see the ERROR records "
                "in the dataset for the reason."
            )
