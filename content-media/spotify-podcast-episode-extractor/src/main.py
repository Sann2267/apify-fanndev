"""Spotify Podcast Episode Extractor -- Apify actor entry point."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apify import Actor

from src import exporters
from src.constants import REQUEST_DELAY
from src.entities import dig, envelope, error_record
from src.episodes import parse_episode, parse_show
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.spotify import NotFound, SpotifyClient, SpotifyError, UnexpectedShape
from src.uris import BadReference, parse_reference, url_of
from src.input_errors import input_error

SOURCE_SHOW = "pathfinder-queryShowMetadataV2"
SOURCE_EPISODES = "pathfinder-queryPodcastEpisodes"
SOURCE_EPISODE = "pathfinder-getEpisodeOrChapter"
SOURCE_SEARCH = "pathfinder-searchSuggestions"

PAGE_SIZE = 100

COLUMNS = [
    "episodeName", "showName", "publisher", "releaseDate", "duration",
    "durationMinutes", "guestHints", "chapterCount", "sponsorDomains",
    "hasVideo", "hasTranscript", "explicit", "episodeNumberHint",
    "episodeUrl", "shareUrl", "description", "recordType",
]


def within(record: dict, since: str | None, until: str | None) -> bool:
    released = record.get("releaseDate")
    if not released:
        return not (since or until)
    if since and released < since:
        return False
    if until and released > until:
        return False
    return True


async def resolve_show(client: SpotifyClient, text: str) -> tuple[str, str]:
    """Find a show id by name through the web player's own search."""
    for hit in await client.suggest(text):
        if hit["kind"] in ("Podcast", "Show"):
            uri = hit["data"].get("uri") or ""
            identifier = uri.split(":")[-1]
            if identifier:
                return identifier, hit["data"].get("name") or text
    # A search for a show name very often surfaces one of its episodes first.
    for hit in await client.suggest(text):
        if hit["kind"] == "Episode":
            uri = dig(hit["data"], "podcastV2", "data", "uri") or ""
            identifier = uri.split(":")[-1]
            if identifier:
                return identifier, dig(hit["data"], "podcastV2", "data", "name") or text
    raise NotFound(f"No Spotify podcast matched {text!r}.")


async def read_show(
    client: SpotifyClient,
    show_id: str,
    max_episodes: int,
    mine: bool,
    since: str | None,
    until: str | None,
    log,
) -> tuple[dict, list[dict]]:
    metadata = await client.entity(
        "queryShowMetadataV2", {"uri": f"spotify:show:{show_id}"}, "podcastUnionV2"
    )
    show = parse_show(metadata)

    episodes: list[dict] = []
    offset = 0
    total = 0
    stop_early = False
    while len(episodes) < max_episodes and not stop_early:
        payload = await client.entity(
            "queryPodcastEpisodes",
            {"uri": f"spotify:show:{show_id}", "offset": offset, "limit": PAGE_SIZE},
            "podcastUnionV2",
        )
        # The show metadata query returns a single sample episode and no count;
        # only the episode query knows how many there are, so the show record
        # gets its episodeCount from here rather than from its own payload.
        total = dig(payload, "episodesV2", "totalCount") or total
        show["episodeCount"] = total or show.get("episodeCount")
        page = dig(payload, "episodesV2", "items", default=[]) or []
        if not page:
            break
        for item in page:
            data = dig(item, "entity", "data") or {}
            if not data.get("uri"):
                continue
            record = parse_episode(data, mine)
            if within(record, since, until):
                episodes.append(record)
            elif since and record.get("releaseDate") and record["releaseDate"] < since:
                # Episodes come newest first, so once one is older than the
                # window every later one is too. Paging on would download the
                # whole back catalogue to discard it.
                stop_early = True
                break
        offset += len(page)
        if total and offset >= total:
            break
        if len(episodes) < max_episodes and not stop_early:
            if log and total > PAGE_SIZE:
                log.info(f"  {min(offset, total)}/{total} episodes scanned")
            await asyncio.sleep(REQUEST_DELAY)

    return show, episodes[:max_episodes]


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        references = dedupe(
            string_list(actor_input.get("showUrls"))
            + string_list(actor_input.get("showNames"))
            + string_list(actor_input.get("episodeUrls"))
            + string_list(actor_input.get("startUrls"))
        )
        if not references:
            raise input_error(
                "Nothing to do. Supply showUrls (for example "
                "https://open.spotify.com/show/4rOoJ6Egrf8K2IrywzwOMk), showNames "
                "to look up by name, or episodeUrls for individual episodes."
            )

        max_episodes = clamp(actor_input.get("maxEpisodesPerShow", 100), 1, 5000, 100)
        mine = bool(actor_input.get("mineDescriptions", True))
        include_show = bool(actor_input.get("includeShowRecord", True))
        since = (actor_input.get("releasedAfter") or "").strip()[:10] or None
        until = (actor_input.get("releasedBefore") or "").strip()[:10] or None
        export_formats = actor_input.get("exportFormats") or []

        for label, value in (("releasedAfter", since), ("releasedBefore", until)):
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError as exc:
                    raise input_error(f"{label} must be YYYY-MM-DD, got {value!r}.") from exc

        exporters.configure(
            preferred=COLUMNS,
            skip={"chapters", "links", "mentionedHandles", "mediaTypes",
                  "showDescription", "topics"},
            sheet="Podcast episodes",
            stem="spotify-podcast-episodes",
        )

        proxy_url = await proxy_url_from(Actor, actor_input)
        records: list[dict] = []
        errors: list[dict] = []
        episode_total = 0

        async with SpotifyClient(proxy_url=proxy_url, log=Actor.log) as client:
            for position, reference in enumerate(references, start=1):
                Actor.log.info(f"[{position}/{len(references)}] {reference}")
                try:
                    kind = identifier = None
                    try:
                        kind, identifier = parse_reference(reference)
                    except BadReference:
                        identifier, matched = await resolve_show(client, reference)
                        kind = "show"
                        Actor.log.info(f"  matched {matched!r}")

                    if kind == "episode":
                        data = await client.entity(
                            "getEpisodeOrChapter",
                            {"uri": f"spotify:episode:{identifier}"},
                            "episodeUnionV2",
                        )
                        record = parse_episode(data, mine)
                        record["showName"] = dig(data, "podcastV2", "data", "name")
                        record["showUrl"] = dig(data, "podcastV2", "data", "uri")
                        records.append(
                            envelope(reference, SOURCE_EPISODE, "EPISODE", record)
                        )
                        episode_total += 1
                        Actor.log.info(f"  {record.get('episodeName')!r}")
                        await asyncio.sleep(REQUEST_DELAY)
                        continue

                    if kind != "show":
                        message = (
                            f"{url_of(kind, identifier)} is a Spotify {kind}. This "
                            f"actor reads podcasts and episodes."
                        )
                        Actor.log.warning(f"  {message}")
                        errors.append(error_record(reference, "unsupported_entity", message))
                        continue

                    show, episodes = await read_show(
                        client, identifier, max_episodes, mine, since, until, Actor.log
                    )
                except NotFound as exc:
                    Actor.log.warning(f"  {exc}")
                    errors.append(error_record(reference, "not_found", str(exc)))
                    continue
                except (SpotifyError, UnexpectedShape) as exc:
                    Actor.log.warning(f"  failed: {exc}")
                    errors.append(error_record(reference, "fetch_failed", str(exc)))
                    continue

                rating = show.get("averageRating")
                Actor.log.info(
                    f"  {show.get('showName')!r} by {show.get('publisher')}: "
                    f"{len(episodes)} episode(s) of {show.get('episodeCount')}"
                    + (f", rated {rating}" if rating else "")
                )
                if include_show:
                    records.append(envelope(reference, SOURCE_SHOW, "SHOW", show))

                context = {
                    "showName": show.get("showName"),
                    "showId": show.get("showId"),
                    "showUrl": show.get("showUrl"),
                    "publisher": show.get("publisher"),
                }
                for episode in episodes:
                    episode.update(context)
                    records.append(
                        envelope(reference, SOURCE_EPISODES, "EPISODE", episode)
                    )
                episode_total += len(episodes)
                await asyncio.sleep(REQUEST_DELAY)

            requests_made = client.requests_made

        ordered = records + errors
        for record in ordered:
            await Actor.push_data(record)
        await exporters.write_exports(Actor, export_formats, ordered)

        with_chapters = sum(1 for r in records if (r.get("chapterCount") or 0) > 0)
        Actor.log.info(
            f"Finished: {episode_total} episode(s) in {requests_made} request(s) | "
            f"{with_chapters} with chapter timestamps | {len(errors)} failure(s)"
        )
        if errors and not episode_total:
            raise RuntimeError(
                "Nothing collected and every input failed -- see the ERROR records "
                "in the dataset for the reason."
            )
