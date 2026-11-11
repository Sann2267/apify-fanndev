"""Mode dispatch for the YouTube sponsor & affiliate Actor.

* ``video``     -- one or more watch URLs / IDs. One record per video.
* ``channel``   -- a handle, resolved to its newest N videos, then as above.
* ``reference`` -- probes the surface and reports what it actually yielded,
  including how many attempts the reduced page cost. Run this first when a
  result looks wrong; it is the cheapest way to tell a gated page apart from a
  video that genuinely has no description.

Every record says how it was obtained (``_source``, ``_attempts``) because on
this source a 200 is not proof of anything -- see ``src/constants.py``.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, NotFound, Reduced, YouTubeClient
from src.constants import MARKER_DATA, MARKER_DESCRIPTION, MODES, URL_CHANNEL_VIDEOS, URL_WATCH
from src.extractor import NoPlayerResponse, build_record, parse_channel_video_ids, parse_video
from src.input_errors import input_error

log = logging.getLogger(__name__)

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _video_id(raw: str) -> str | None:
    """Accept a bare ID, a watch URL, a youtu.be link or a /shorts/ link."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if VIDEO_ID.fullmatch(raw):
        return raw
    for pattern in (r"[?&]v=([A-Za-z0-9_-]{11})",
                    r"youtu\.be/([A-Za-z0-9_-]{11})",
                    r"/shorts/([A-Za-z0-9_-]{11})",
                    r"/live/([A-Za-z0-9_-]{11})",
                    r"/embed/([A-Za-z0-9_-]{11})"):
        found = re.search(pattern, raw)
        if found:
            return found.group(1)
    return None


def _handle(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if raw.startswith("http"):
        raw = re.sub(r"^https?://(www\.)?youtube\.com/", "", raw)
        raw = raw.split("/")[0]
    if raw and not raw.startswith(("@", "channel/", "c/", "user/")):
        raw = "@" + raw.lstrip("@")
    return raw


def _envelope(payload: dict, *, source: str, query: str, record_type: str,
              attempts: int | None = None) -> dict:
    return {
        "_input": query,
        "_query": query,
        "_source": source,
        "_scrapedAt": _now(),
        "_attempts": attempts,
        "recordType": record_type,
        **payload,
    }


async def _one_video(client: YouTubeClient, video_id: str) -> dict:
    """Fetch and classify a single video, or explain why we could not."""
    url = URL_WATCH.format(video_id=video_id)
    try:
        body, profile, attempts = await client.get(url, marker=MARKER_DESCRIPTION)
    except Reduced as exc:
        # The important branch: 200 every time, payload never served.
        return _envelope(
            {"videoId": video_id, "error": "reduced-page", "message": str(exc),
             "hint": "YouTube served a real page without the player response on every "
                     "attempt. Retry later or route the run through a residential proxy; "
                     "this is not proof the video lacks a description."},
            source="youtube-watch", query=video_id, record_type="REDUCED",
            attempts=client.attempts_used,
        )
    except NotFound:
        return _envelope({"videoId": video_id, "error": "not-found"},
                         source="youtube-watch", query=video_id, record_type="ERROR")
    except Blocked as exc:
        return _envelope({"videoId": video_id, "error": "blocked", "message": str(exc)},
                         source="youtube-watch", query=video_id, record_type="ERROR")

    try:
        video = parse_video(body)
    except NoPlayerResponse as exc:
        return _envelope({"videoId": video_id, "error": "parse-failed", "message": str(exc)},
                         source="youtube-watch", query=video_id, record_type="REDUCED",
                         attempts=attempts)

    record = build_record(video)
    record["_tlsProfile"] = profile
    return _envelope(record, source="youtube-watch", query=video_id,
                     record_type="VIDEO", attempts=attempts)


async def _run_video_mode(client, actor_inputs: list[str], concurrency: int) -> int:
    ids: list[str] = []
    for raw in actor_inputs:
        video_id = _video_id(raw)
        if video_id and video_id not in ids:
            ids.append(video_id)
        elif not video_id:
            await Actor.push_data(_envelope(
                {"error": "unparseable-input",
                 "message": "Expected a video ID, watch URL, youtu.be or /shorts/ link."},
                source="none", query=raw, record_type="ERROR"))

    semaphore = asyncio.Semaphore(concurrency)

    async def worker(video_id: str) -> dict:
        async with semaphore:
            return await _one_video(client, video_id)

    pushed = 0
    for coro in asyncio.as_completed([worker(v) for v in ids]):
        await Actor.push_data(await coro)
        pushed += 1
    return pushed


async def _run_channel_mode(client, handles: list[str], per_channel: int,
                            concurrency: int) -> int:
    pushed = 0
    for raw in handles:
        handle = _handle(raw)
        if not handle:
            continue
        url = URL_CHANNEL_VIDEOS.format(handle=handle)
        try:
            body, _, attempts = await client.get(url, marker=MARKER_DATA)
        except (Reduced, NotFound, Blocked) as exc:
            await Actor.push_data(_envelope(
                {"channelHandle": handle, "error": type(exc).__name__.lower(),
                 "message": str(exc)},
                source="youtube-channel-videos", query=handle, record_type="ERROR"))
            pushed += 1
            continue

        ids = parse_channel_video_ids(body, per_channel)
        log.info("%s -> %d video(s) in %d attempt(s)", handle, len(ids), attempts)
        if not ids:
            await Actor.push_data(_envelope(
                {"channelHandle": handle, "error": "no-videos-listed",
                 "hint": "The channel page carried ytInitialData but no video IDs."},
                source="youtube-channel-videos", query=handle, record_type="ERROR"))
            pushed += 1
            continue

        semaphore = asyncio.Semaphore(concurrency)

        async def worker(video_id: str, channel=handle) -> dict:
            async with semaphore:
                record = await _one_video(client, video_id)
                record["channelHandle"] = channel
                record["_input"] = channel
                return record

        for coro in asyncio.as_completed([worker(v) for v in ids]):
            await Actor.push_data(await coro)
            pushed += 1
    return pushed


async def _run_reference(client) -> int:
    """Measure the surface instead of describing it."""
    probes = []
    for video_id in ("dQw4w9WgXcQ", "jNQXAC9IVRw"):
        try:
            body, profile, attempts = await client.get(
                URL_WATCH.format(video_id=video_id), marker=MARKER_DESCRIPTION)
            video = parse_video(body)
            probes.append({
                "videoId": video_id, "ok": True, "attempts": attempts,
                "tlsProfile": profile, "pageBytes": len(body),
                "descriptionBytes": len(video["description"]),
                "captionLanguages": video["captionLanguages"],
            })
        except Exception as exc:
            probes.append({"videoId": video_id, "ok": False,
                           "attempts": client.attempts_used,
                           "error": f"{type(exc).__name__}: {exc}"})

    await Actor.push_data(_envelope(
        {
            "surface": "youtube.com/watch -> ytInitialPlayerResponse",
            "probes": probes,
            "known": {
                "descriptionIsFullText": True,
                "reducedPageIsCommon": True,
                "transcriptReadable": False,
                "transcriptNote": "captionTracks lists the languages, but each signed "
                                  "baseUrl answers 200 with a zero-byte body; InnerTube "
                                  "/player answers 400 (ANDROID/IOS) or UNPLAYABLE (WEB). "
                                  "This Actor reports caption languages only.",
            },
        },
        source="reference", query="reference", record_type="SURFACE"))
    return 1


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        mode = (actor_input.get("mode") or "video").strip()
        if mode not in MODES:
            raise input_error(f"mode must be one of {MODES}, got {mode!r}")

        concurrency = max(1, min(int(actor_input.get("concurrency") or 4), 10))
        per_channel = max(1, min(int(actor_input.get("videosPerChannel") or 15), 100))

        proxy_url = None
        proxy_config = actor_input.get("proxyConfiguration")
        if proxy_config:
            configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_config)
            if configuration:
                proxy_url = await configuration.new_url()

        client = YouTubeClient(proxy_url=proxy_url, profile=actor_input.get("tlsProfile"))

        if mode == "reference":
            pushed = await _run_reference(client)
        elif mode == "channel":
            handles = actor_input.get("channels") or []
            if not handles:
                raise input_error("channel mode needs at least one entry in `channels`.")
            pushed = await _run_channel_mode(client, handles, per_channel, concurrency)
        else:
            videos = actor_input.get("videos") or []
            if not videos:
                raise input_error("video mode needs at least one entry in `videos`.")
            pushed = await _run_video_mode(client, videos, concurrency)

        log.info("pushed %d record(s) in mode=%s", pushed, mode)
