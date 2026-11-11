"""Spotify Bulk Text-to-URI Matcher -- Apify actor entry point."""

from __future__ import annotations

import asyncio

from apify import Actor

from src import exporters
from src.constants import REQUEST_DELAY
from src.entities import envelope, error_record
from src.matcher import best_match, parse_entry
from src.runtime import clamp, proxy_url_from
from src.spotify import SpotifyClient, SpotifyError, UnexpectedShape
from src.uris import BadReference, parse_reference, url_of
from src.input_errors import input_error

SOURCE = "pathfinder-searchSuggestions"

COLUMNS = [
    "inputLine", "matched", "matchConfidence", "matchScore", "trackName",
    "artistName", "albumName", "duration", "trackUri", "trackUrl",
    "queryTitle", "queryArtist", "titleScore", "artistScore",
    "bestGuessName", "bestGuessArtist", "unmatchedReason", "recordType",
]


def collect_entries(actor_input: dict) -> list:
    """Every accepted input shape, flattened into one ordered list."""
    entries: list = []

    text = actor_input.get("queriesText")
    if isinstance(text, str):
        entries.extend(line for line in (l.strip() for l in text.splitlines()) if line)

    for item in actor_input.get("queries") or []:
        if isinstance(item, dict):
            entries.append(item)
        elif str(item or "").strip():
            entries.append(str(item).strip())

    for item in actor_input.get("tracks") or []:
        if isinstance(item, dict):
            entries.append(item)

    return entries


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        entries = collect_entries(actor_input)
        if not entries:
            raise input_error(
                "Nothing to match. Paste one track per line into queriesText "
                "(for example 'Bohemian Rhapsody - Queen'), or supply queries "
                "as a list, or tracks as objects with title and artist."
            )

        max_queries = clamp(actor_input.get("maxQueries", 1000), 1, 20000, 1000)
        minimum = float(actor_input.get("minimumMatchScore", 0.70) or 0.70)
        minimum = max(0.0, min(1.0, minimum))
        emit_unmatched = bool(actor_input.get("emitUnmatched", True))
        export_formats = actor_input.get("exportFormats") or []

        entries = entries[:max_queries]
        exporters.configure(
            preferred=COLUMNS,
            skip={"artistNames"},
            sheet="Matched tracks",
            stem="spotify-uri-matches",
        )

        proxy_url = await proxy_url_from(Actor, actor_input)
        records: list[dict] = []
        errors: list[dict] = []
        matched = 0

        async with SpotifyClient(proxy_url=proxy_url, log=Actor.log) as client:
            for position, raw_entry in enumerate(entries, start=1):
                entry = parse_entry(raw_entry)
                if not entry["title"]:
                    errors.append(
                        error_record(entry["raw"], "empty_query", "No searchable text.")
                    )
                    continue

                # A line that is already a Spotify link or URI needs no search.
                try:
                    kind, identifier = parse_reference(entry["raw"])
                except BadReference:
                    kind = identifier = None
                if kind == "track":
                    records.append(
                        envelope(
                            entry["raw"], "input-passthrough", "MATCH",
                            {
                                "inputLine": entry["raw"],
                                "matched": True,
                                "matchConfidence": "exact",
                                "matchScore": 1.0,
                                "trackId": identifier,
                                "trackUri": f"spotify:track:{identifier}",
                                "trackUrl": url_of("track", identifier),
                                "note": "Input was already a Spotify track reference; "
                                        "no search was needed.",
                            },
                        )
                    )
                    matched += 1
                    continue

                try:
                    hits = await client.suggest(
                        " ".join(p for p in (entry["title"], entry["artist"]) if p)
                    )
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  search failed for {entry['raw']!r}: {exc}")
                    errors.append(error_record(entry["raw"], "search_failed", str(exc)))
                    continue

                result = best_match(entry, hits, minimum)
                result["inputLine"] = entry["raw"]
                if result["matched"]:
                    matched += 1
                elif not emit_unmatched:
                    continue
                records.append(envelope(entry["raw"], SOURCE, "MATCH", result))

                if position % 25 == 0 or position == len(entries):
                    Actor.log.info(
                        f"  {position}/{len(entries)} processed, {matched} matched"
                    )
                await asyncio.sleep(REQUEST_DELAY)

            requests_made = client.requests_made

        ordered = records + errors
        for record in ordered:
            await Actor.push_data(record)
        await exporters.write_exports(Actor, export_formats, ordered)

        uris = [r["trackUri"] for r in records if r.get("matched") and r.get("trackUri")]
        if uris:
            store = await Actor.open_key_value_store()
            await store.set_value(
                "matched-uris.txt", "\n".join(uris).encode("utf-8"), content_type="text/plain"
            )
            Actor.log.info(f"Wrote matched-uris.txt ({len(uris)} URIs, one per line).")

        by_confidence: dict[str, int] = {}
        for record in records:
            by_confidence[record.get("matchConfidence", "none")] = (
                by_confidence.get(record.get("matchConfidence", "none"), 0) + 1
            )
        breakdown = ", ".join(f"{count} {name}" for name, count in sorted(by_confidence.items()))
        Actor.log.info(
            f"Finished: {matched}/{len(entries)} matched in {requests_made} request(s) "
            f"| {breakdown} | {len(errors)} failure(s)"
        )
        if errors and not records:
            raise RuntimeError(
                "Nothing matched and every query failed -- see the ERROR records "
                "in the dataset for the reason."
            )
