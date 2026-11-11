"""Facebook Reels & Video Metadata / Transcript Extractor -- Apify actor entry point."""

from __future__ import annotations

from apify import Actor

from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession
from src.parser import matches_filters, page_ref, summarise, video_id
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.videos import PageUnavailable, add_transcript, fetch_single, fetch_tab
from src.input_errors import input_error

SOURCE = "reels-and-videos"


def read_targets(actor_input: dict) -> tuple[list[str], list[str]]:
    """Split the input into page slugs and individual video ids."""
    slugs: list[str] = []
    ids: list[str] = []
    for key in ("pages", "videoUrls", "startUrls"):
        for item in actor_input.get(key) or []:
            value = str((item.get("url") if isinstance(item, dict) else item) or "")
            found = video_id(value)
            if found:
                ids.append(found)
                continue
            slug = page_ref(value)
            if slug:
                slugs.append(slug)
            elif value.strip():
                Actor.log.warning(
                    f"Skipping {value!r}: it is neither a page slug nor a video/reel URL."
                )
    return list(dict.fromkeys(slugs)), list(dict.fromkeys(ids))


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        slugs, ids = read_targets(actor_input)
        if not slugs and not ids:
            raise input_error(
                "Nothing to scrape. Supply pages (slugs or page URLs) to read their "
                "reels and videos tabs, or videoUrls (reel URLs, watch URLs or bare "
                "numeric video ids)."
            )

        tabs = actor_input.get("tabs") or ["reels", "videos"]
        tabs = [t for t in tabs if t in ("reels", "videos")] or ["reels"]
        max_videos = max(1, min(int(actor_input.get("maxVideosPerTab", 20)), 500))
        fetch_transcripts = bool(actor_input.get("fetchTranscripts", True))
        filters = {
            "onlyReels": bool(actor_input.get("onlyReels")),
            "onlyWithCaptions": bool(actor_input.get("onlyWithCaptions")),
            "minPlays": actor_input.get("minPlays"),
            "captionContains": actor_input.get("captionContains"),
        }
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(
            f"{len(slugs)} page(s) x {len(tabs)} tab(s) and {len(ids)} direct video(s). "
            "Reels tabs are large (~13 MB each)."
        )

        records: list[dict] = []
        kept: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for slug in slugs:
                for tab in tabs:
                    label = f"{slug}/{tab}"
                    try:
                        videos, meta = await fetch_tab(
                            session, slug, tab, max_videos, log=Actor.log
                        )
                    except (PageUnavailable, BlockedError) as exc:
                        failures += 1
                        record = error_record(SOURCE, label, "tab_unavailable", str(exc))
                        records.append(record)
                        await Actor.push_data(record)
                        continue
                    except Exception as exc:
                        failures += 1
                        record = error_record(
                            SOURCE, label, "unexpected_error",
                            f"{type(exc).__name__}: {exc}",
                        )
                        records.append(record)
                        await Actor.push_data(record)
                        continue

                    if meta.get("paginationUnavailable"):
                        Actor.log.warning(
                            f"{label}: kept the {len(videos)} rendered video(s); "
                            "Facebook's pagination query could not be replayed this run."
                        )

                    for video in videos:
                        if fetch_transcripts:
                            await add_transcript(session, video)
                        if not matches_filters(video, filters):
                            continue
                        record = {
                            **envelope(SOURCE, label, "VIDEO"),
                            **video,
                            "sourceTab": tab,
                            "sourceSlug": slug,
                        }
                        records.append(record)
                        kept.append(video)
                        await Actor.push_data(record)

                    Actor.log.info(
                        f"{label}: {len(videos)} video(s) in {meta['requestsMade']} request(s)"
                    )

            for vid in ids:
                try:
                    video = await fetch_single(session, vid)
                except (PageUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, vid, "video_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                if fetch_transcripts:
                    await add_transcript(session, video)
                if not matches_filters(video, filters):
                    continue
                record = {
                    **envelope(SOURCE, vid, "VIDEO"),
                    **video,
                    "sourceTab": "direct",
                    "sourceSlug": None,
                }
                records.append(record)
                kept.append(video)
                await Actor.push_data(record)

        if emit_summary and kept:
            stats = summarise(kept)
            summary = {
                **envelope(SOURCE, f"{len(slugs)} page(s), {len(ids)} video(s)", "RUN_SUMMARY"),
                **stats,
                "failures": failures,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {stats['videosCollected']} video(s), "
                f"{stats['reels']} reel(s), {stats['withCaptions']} with captions, "
                f"{stats['withTranscript']} transcribed, median plays "
                f"{stats['medianPlays']}"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept)} video(s) | {failures} failure(s)")
        if failures and not kept:
            raise RuntimeError(
                "Nothing could be read and nothing was collected -- see the ERROR records."
            )
