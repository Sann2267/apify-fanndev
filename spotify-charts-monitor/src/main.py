"""Spotify Global & Regional Charts Monitor -- Apify actor entry point."""

from __future__ import annotations

import asyncio

from apify import Actor

from src import catalog, exporters
from src.charts import (
    fetch_public_charts,
    parse_chart_entries,
    parse_chart_header,
    summarise,
)
from src.constants import REQUEST_DELAY
from src.entities import envelope, error_record, utc_now_iso
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.spotify import NotFound, SpotifyClient, SpotifyError, UnexpectedShape
from src.tracking import (
    SNAPSHOT_KEY,
    apply_movement,
    build_entry,
    dropped_out,
    previous_for,
    snapshot_key,
)
from src.uris import BadReference, parse_reference
from src.input_errors import input_error

SOURCE_PLAYLIST = "pathfinder-fetchPlaylist"
SOURCE_PUBLIC = "charts-public-v0"

COLUMNS = [
    "chartName", "country", "recurrence", "rank", "previousRank", "rankChange",
    "entryStatus", "trackName", "artistName", "albumName", "playcount",
    "entityType", "entityName", "peakRank", "appearancesOnChart",
    "chartDate", "chartLastUpdated", "trackUrl", "recordType",
]


async def read_playlist_chart(
    client: SpotifyClient, chart_id: str, country: str, recurrence: str
) -> tuple[dict, list[dict]]:
    payload = await client.entity(
        "fetchPlaylist",
        {"uri": f"spotify:playlist:{chart_id}", "offset": 0, "limit": 100,
         "enableWatchFeedEntrypoint": False},
        "playlistV2",
    )
    return parse_chart_header(payload, country, recurrence), parse_chart_entries(payload)


def retired_note(chart_id: str) -> str | None:
    name = catalog.RETIRED.get(chart_id)
    if not name:
        return None
    return (
        f"{name} was discontinued by Spotify. Its playlist id still answers with "
        f"HTTP 200, but the playlist behind it no longer exists. Spotify retired "
        f"the Viral 50 charts; the Top 50 and Top Songs charts are unaffected."
    )


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        countries = [c.strip().upper() for c in string_list(actor_input.get("countries"))]
        recurrence = (actor_input.get("recurrence") or "daily").strip().lower()
        if recurrence not in catalog.RECURRENCES:
            raise input_error(
                f"recurrence must be one of {', '.join(catalog.RECURRENCES)}, "
                f"got {recurrence!r}."
            )
        include_public = bool(actor_input.get("includeGlobalWeeklyCharts", True))
        extra = dedupe(string_list(actor_input.get("playlistUrls")))
        max_entries = clamp(actor_input.get("maxEntriesPerChart", 50), 1, 200, 50)
        track_movement = bool(actor_input.get("trackRankMovement", True))
        store_name = (actor_input.get("trackingStoreName") or "spotify-charts-monitor").strip()
        emit_summary = bool(actor_input.get("emitChartSummary", True))
        export_formats = actor_input.get("exportFormats") or []

        if not countries and not extra and not include_public:
            raise input_error(
                "Nothing to do. Pick at least one country (for example "
                "['GLOBAL', 'ID', 'US']), supply playlistUrls, or leave "
                "includeGlobalWeeklyCharts on."
            )

        unknown = [c for c in countries if not catalog.resolve(c, recurrence)]
        if unknown:
            raise input_error(
                f"No {recurrence} Spotify chart is published for "
                f"{', '.join(unknown)}. Available {recurrence} charts: "
                f"{', '.join(catalog.available(recurrence))}."
            )

        exporters.configure(
            preferred=COLUMNS,
            skip={"artistNames", "newEntryNames", "labels", "songwriters", "producers"},
            sheet="Chart entries",
            stem="spotify-charts",
        )

        snapshot = None
        store = None
        if track_movement:
            store = await Actor.open_key_value_store(name=store_name)
            snapshot = await store.get_value(SNAPSHOT_KEY) or {"charts": {}}
            if snapshot.get("charts"):
                Actor.log.info(
                    f"Comparing against the previous run stored in {store_name!r}."
                )
            else:
                Actor.log.info(
                    f"No previous run in {store_name!r} -- this run is the baseline, "
                    f"so entries are marked BASELINE rather than NEW_ENTRY."
                )

        proxy_url = await proxy_url_from(Actor, actor_input)
        records: list[dict] = []
        errors: list[dict] = []
        new_snapshot: dict = {"capturedAt": utc_now_iso(), "charts": {}}
        charts_read = 0

        async with SpotifyClient(proxy_url=proxy_url, log=Actor.log) as client:
            # -- 1. country charts from editorial playlists -----------------
            targets = [(country, catalog.resolve(country, recurrence)) for country in countries]
            for reference in extra:
                try:
                    kind, identifier = parse_reference(reference, default_kind="playlist")
                    if kind != "playlist":
                        raise BadReference(f"{reference!r} is a Spotify {kind}, not a playlist.")
                    targets.append(("CUSTOM", identifier))
                except BadReference as exc:
                    Actor.log.warning(f"  {exc}")
                    errors.append(error_record(reference, "unparsable_input", str(exc)))

            for position, (country, chart_id) in enumerate(targets, start=1):
                label = f"{country} {recurrence}"
                Actor.log.info(f"[{position}/{len(targets)}] {label}")
                try:
                    header, entries = await read_playlist_chart(
                        client, chart_id, country, recurrence
                    )
                except NotFound as exc:
                    detail = retired_note(chart_id) or str(exc)
                    Actor.log.warning(f"  {detail}")
                    errors.append(error_record(label, "chart_not_found", detail))
                    continue
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  failed: {exc}")
                    errors.append(error_record(label, "fetch_failed", str(exc)))
                    continue

                entries = entries[:max_entries]
                key = snapshot_key(country, recurrence, chart_id)
                if track_movement:
                    apply_movement(entries, previous_for(snapshot, key))
                    new_snapshot["charts"][key] = build_entry(entries, new_snapshot["capturedAt"])

                context = {
                    "chartName": header["chartName"],
                    "chartId": header["chartId"],
                    "chartUrl": header["chartUrl"],
                    "country": country,
                    "recurrence": recurrence,
                    "chartLastUpdated": header.get("chartLastUpdated"),
                }
                for entry in entries:
                    entry.update(context)
                    records.append(
                        envelope(label, SOURCE_PLAYLIST, "CHART_ENTRY", entry)
                    )

                if track_movement:
                    for gone in dropped_out(entries, previous_for(snapshot, key)):
                        gone.update(context)
                        records.append(
                            envelope(label, SOURCE_PLAYLIST, "CHART_EXIT", gone)
                        )

                if emit_summary:
                    records.append(
                        envelope(
                            label, SOURCE_PLAYLIST, "CHART_SUMMARY",
                            {**header, **summarise(entries)},
                        )
                    )

                charts_read += 1
                movement = summarise(entries)
                Actor.log.info(
                    f"  {header['chartName']}: {len(entries)} entries, "
                    f"{movement['newEntries']} new, {movement['climbers']} up, "
                    f"{movement['fallers']} down"
                )
                await asyncio.sleep(REQUEST_DELAY)

            # -- 2. the tokenless public charts service ---------------------
            if include_public:
                Actor.log.info("Reading the public global weekly charts...")
                try:
                    for chart in await fetch_public_charts(client):
                        header = chart["header"]
                        entries = chart["entries"][:max_entries]
                        context = {
                            "chartName": header["chartName"],
                            "chartAlias": header.get("chartAlias"),
                            "chartDate": header.get("chartDate"),
                            "country": header.get("country"),
                            "recurrence": header.get("recurrence"),
                        }
                        for entry in entries:
                            entry.update(context)
                            records.append(
                                envelope(
                                    header.get("chartAlias") or "public",
                                    SOURCE_PUBLIC, "CHART_ENTRY", entry,
                                )
                            )
                        if emit_summary:
                            records.append(
                                envelope(
                                    header.get("chartAlias") or "public",
                                    SOURCE_PUBLIC, "CHART_SUMMARY",
                                    {**header, **summarise(entries)},
                                )
                            )
                        charts_read += 1
                        Actor.log.info(f"  {header['chartName']}: {len(entries)} entries")
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  public charts failed: {exc}")
                    errors.append(error_record("public-charts", "fetch_failed", str(exc)))

            requests_made = client.requests_made

        ordered = records + errors
        for record in ordered:
            await Actor.push_data(record)

        if track_movement and store is not None and new_snapshot["charts"]:
            await store.set_value(SNAPSHOT_KEY, new_snapshot)
            Actor.log.info(f"Saved this run's chart order to {store_name!r}.")

        await exporters.write_exports(Actor, export_formats, ordered)

        entries_total = sum(1 for r in records if r["recordType"] == "CHART_ENTRY")
        Actor.log.info(
            f"Finished: {charts_read} chart(s), {entries_total} entries in "
            f"{requests_made} request(s) | {len(errors)} failure(s)"
        )
        if errors and not records:
            raise RuntimeError(
                "Nothing collected and every chart failed -- see the ERROR records "
                "in the dataset for the reason."
            )
