"""Mode dispatch for the YouTube Shorts trend tracker.

* ``hashtag``   -- the ranked Shorts grid for each hashtag, optionally enriched
  with per-Short figures.
* ``video``     -- per-Short figures for IDs you already have.
* ``reference`` -- probe both surfaces and report what they yielded.

The grid's position order *is* the trend signal, so ``gridPosition`` rides along
on every record and the enrichment step never reorders anything.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, NotFound, Reduced, YouTubeClient
from src.constants import (
    MARKER_DATA,
    MARKER_LOCKUP,
    MODES,
    URL_HASHTAG,
    URL_SHORT,
)
from src.extractor import parse_hashtag_grid, parse_short_detail
from src.input_errors import input_error

log = logging.getLogger(__name__)

URL_WATCH = "https://www.youtube.com/watch?v={video_id}"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _video_id(raw: str) -> str | None:
    raw = (raw or "").strip()
    if VIDEO_ID.fullmatch(raw):
        return raw
    for pattern in (r"/shorts/([A-Za-z0-9_-]{11})", r"[?&]v=([A-Za-z0-9_-]{11})",
                    r"youtu\.be/([A-Za-z0-9_-]{11})"):
        found = re.search(pattern, raw)
        if found:
            return found.group(1)
    return None


def _clean_tag(raw: str) -> str:
    raw = (raw or "").strip().lstrip("#")
    if raw.startswith("http"):
        found = re.search(r"/hashtag/([^/?#]+)", raw)
        raw = found.group(1) if found else raw
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


async def _detail(client: YouTubeClient, video_id: str, exact_likes: bool) -> dict:
    """Per-Short figures.

    ``exact_likes`` picks the URL, and that is the whole trade-off: the
    ``/shorts/`` page rounds the like count ("36 thousand"), the ``/watch``
    page does not ("36,212"). Both cost one request; ``/watch`` does not carry
    the sound attribution, so asking for exact likes *and* sound costs two.
    """
    url = URL_WATCH if exact_likes else URL_SHORT
    body, profile, attempts = await client.get(url.format(video_id=video_id),
                                               marker=MARKER_DATA)
    detail = parse_short_detail(body)
    detail["videoId"] = video_id
    detail["url"] = URL_SHORT.format(video_id=video_id)
    detail["_tlsProfile"] = profile
    detail["_detailSurface"] = "watch" if exact_likes else "shorts"

    if exact_likes and detail.get("soundAttribution") is None:
        sound_body, _, _ = await client.get(URL_SHORT.format(video_id=video_id),
                                            marker=MARKER_DATA)
        detail["soundAttribution"] = parse_short_detail(sound_body).get("soundAttribution")
        detail["_detailSurface"] = "watch+shorts"

    return detail, attempts


async def _enrich(client, entries, exact_likes, concurrency, tag=None):
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(entry: dict) -> dict:
        async with semaphore:
            video_id = entry["videoId"]
            if not video_id:
                return _envelope({**entry, "error": "no-video-id"},
                                 source="youtube-hashtag-grid",
                                 query=tag or "", record_type="ERROR")
            try:
                detail, attempts = await _detail(client, video_id, exact_likes)
            except Reduced as exc:
                return _envelope(
                    {**entry, "error": "reduced-page", "message": str(exc),
                     "hint": "YouTube served a page without the payload every time. "
                             "The grid figures in this record are still valid."},
                    source="youtube-shorts-detail", query=tag or video_id,
                    record_type="REDUCED", attempts=client.attempts_used)
            except (NotFound, Blocked) as exc:
                return _envelope({**entry, "error": type(exc).__name__.lower(),
                                  "message": str(exc)},
                                 source="youtube-shorts-detail",
                                 query=tag or video_id, record_type="ERROR")
            merged = {**entry, **detail}
            return _envelope(merged, source="youtube-shorts-detail",
                             query=tag or video_id, record_type="SHORT",
                             attempts=attempts)

    return await asyncio.gather(*[worker(e) for e in entries])


async def _run_hashtag(client, tags, limit, detail, exact_likes, concurrency) -> int:
    pushed = 0
    for raw in tags:
        tag = _clean_tag(raw)
        if not tag:
            continue
        try:
            body, profile, attempts = await client.get(
                URL_HASHTAG.format(tag=tag), marker=MARKER_LOCKUP)
        except (Reduced, NotFound, Blocked) as exc:
            await Actor.push_data(_envelope(
                {"hashtag": tag, "error": type(exc).__name__.lower(), "message": str(exc)},
                source="youtube-hashtag-grid", query=tag, record_type="ERROR"))
            pushed += 1
            continue

        entries = parse_hashtag_grid(body, limit)
        for entry in entries:
            entry["hashtag"] = tag
        log.info("#%s -> %d short(s), %d attempt(s), %s", tag, len(entries), attempts, profile)

        if not entries:
            await Actor.push_data(_envelope(
                {"hashtag": tag, "error": "empty-grid",
                 "hint": "The page loaded but listed no Shorts. Check the hashtag spelling."},
                source="youtube-hashtag-grid", query=tag, record_type="ERROR"))
            pushed += 1
            continue

        if not detail:
            for entry in entries:
                await Actor.push_data(_envelope(
                    entry, source="youtube-hashtag-grid", query=tag,
                    record_type="SHORT", attempts=attempts))
                pushed += 1
            continue

        for record in await _enrich(client, entries, exact_likes, concurrency, tag):
            await Actor.push_data(record)
            pushed += 1
    return pushed


async def _run_video(client, videos, exact_likes, concurrency) -> int:
    entries = []
    for raw in videos:
        video_id = _video_id(raw)
        if video_id:
            entries.append({"videoId": video_id, "gridPosition": None, "hashtag": None})
        else:
            await Actor.push_data(_envelope(
                {"error": "unparseable-input",
                 "message": "Expected a video ID, /shorts/ link or watch URL."},
                source="none", query=raw, record_type="ERROR"))

    pushed = 0
    for record in await _enrich(client, entries, exact_likes, concurrency):
        await Actor.push_data(record)
        pushed += 1
    return pushed


async def _run_reference(client) -> int:
    probe = {"surfaces": []}
    try:
        body, profile, attempts = await client.get(
            URL_HASHTAG.format(tag="cooking"), marker=MARKER_LOCKUP)
        grid = parse_hashtag_grid(body, 100)
        probe["surfaces"].append({
            "surface": "/hashtag/<tag>/shorts",
            "ok": True, "attempts": attempts, "tlsProfile": profile,
            "pageBytes": len(body), "shortsListed": len(grid),
            "note": "Rounded view counts only, no likes. One page per hashtag; "
                    "the grid carries a single continuation token that this "
                    "Actor does not follow.",
        })
        if grid:
            detail, tries = await _detail(client, grid[0]["videoId"], exact_likes=False)
            probe["surfaces"].append({
                "surface": "/shorts/<id>", "ok": True, "attempts": tries,
                "viewCount": detail["viewCount"], "likeCount": detail["likeCount"],
                "likeCountIsApprox": detail["likeCountIsApprox"],
                "soundAttribution": detail["soundAttribution"],
            })
    except Exception as exc:
        probe["surfaces"].append({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    await Actor.push_data(_envelope(probe, source="reference", query="reference",
                                    record_type="SURFACE"))
    return 1


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        mode = (actor_input.get("mode") or "hashtag").strip()
        if mode not in MODES:
            raise input_error(f"mode must be one of {MODES}, got {mode!r}")

        limit = max(1, min(int(actor_input.get("shortsPerHashtag") or 36), 36))
        concurrency = max(1, min(int(actor_input.get("concurrency") or 4), 10))
        detail = actor_input.get("detail", True)
        exact_likes = bool(actor_input.get("exactLikes", False))

        proxy_url = None
        proxy_config = actor_input.get("proxyConfiguration")
        if proxy_config:
            configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_config)
            if configuration:
                proxy_url = await configuration.new_url()

        client = YouTubeClient(proxy_url=proxy_url, profile=actor_input.get("tlsProfile"))

        if mode == "reference":
            pushed = await _run_reference(client)
        elif mode == "video":
            videos = actor_input.get("videos") or []
            if not videos:
                raise input_error("video mode needs at least one entry in `videos`.")
            pushed = await _run_video(client, videos, exact_likes, concurrency)
        else:
            hashtags = actor_input.get("hashtags") or []
            if not hashtags:
                raise input_error("hashtag mode needs at least one entry in `hashtags`.")
            pushed = await _run_hashtag(client, hashtags, limit, detail,
                                        exact_likes, concurrency)

        log.info("pushed %d record(s) in mode=%s", pushed, mode)
