"""Parse Facebook reels and video payloads.

A video's facts are spread over several nodes that share its numeric id:

    {"id": "637979908801309", "browser_native_hd_url": ..., "browser_native_sd_url": ...}
    {"video": {"id": "637979908801309", "first_frame_thumbnail": ...},
     "shareable_url": "https://www.facebook.com/reel/637979908801309",
     "playback_video": {"length_in_second": 39.2, "width": 1080, "height": 1920},
     "video_owner": {"name": "Domino's Pizza", "id": "100064795448235"},
     "play_count_reduced": "292K", "track_title": null,
     "is_original_audio_on_facebook": true}
    {"id": "637979908801309", "captions_url": "...srt", "video_available_captions_locales": [...]}
    {"__typename": "Story", "id": "<base64 ...:VK:637979908801309>",
     "post_id": "1053159700187202", "creation_time": 1737990015, ...}

So the parser walks every dict once, works out which video id it names -- from
`id`, from `video.id`, from a `shareable_url`, or by decoding a base64 story id
-- and files the fields it carries under that video.

Two counts to keep apart:
- `play_count` (videos tab) is an exact integer.
- `play_count_reduced` (reels tab) is Facebook's abbreviation, `"292K"`. It is
  parsed to 292000 and the original string is kept beside it, because 292000 is
  not what Facebook said.
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import dedupe, iter_json_blocks, parse_count, walk

VIDEO_IN_URL = re.compile(
    r"(?:/reel/|/videos/|[?&]v=|/watch/\?v=)(\d{6,})", re.I
)
PAGE_SLUG = re.compile(r"facebook\.com/(?:pg/)?([^/?#]+)", re.I)
RESERVED = {"profile.php", "people", "groups", "events", "marketplace", "watch",
            "ads", "reel", "video", "photo", "search"}
ID_TAIL = re.compile(r"(?:^|:)(\d{8,})$")
SRT_BLOCK = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{1,3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.S,
)


def video_id(value: str) -> str | None:
    """Pull a numeric video id out of a reel URL, watch URL, video URL or bare id."""
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit() and len(value) >= 6:
        return value
    match = VIDEO_IN_URL.search(value)
    return match.group(1) if match else None


def page_ref(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if video_id(value):
        return None
    match = PAGE_SLUG.match(value) or PAGE_SLUG.search(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    if not value or value.lower() in RESERVED:
        return None
    return value


def _decode_story_id(node_id: Any) -> str | None:
    if not isinstance(node_id, str) or len(node_id) < 12:
        return None
    try:
        decoded = base64.b64decode(node_id + "==", validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None
    if not decoded.startswith(("S:", "feedback:")):
        return None
    match = ID_TAIL.search(decoded)
    return match.group(1) if match else None


def _iso(stamp: Any) -> str | None:
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return None
    if not 946_684_800 < stamp < 4_102_444_800:
        return None
    return (
        datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.replace(",", "").strip())
        except ValueError:
            return None
    if isinstance(value, dict):
        return _int(value.get("count"))
    return None


def _blank(vid: str) -> dict:
    return {
        "videoId": vid,
        "permalinkUrl": None,
        "isReel": None,
        "pageName": None,
        "pageId": None,
        "pageUrl": None,
        "title": None,
        "caption": None,
        "postId": None,
        "createdAt": None,
        "createdAtIso": None,
        "playCount": None,
        "playCountLabel": None,
        "reactionCount": None,
        "commentCount": None,
        "shareCount": None,
        "lengthSeconds": None,
        "width": None,
        "height": None,
        "trackTitle": None,
        "isOriginalAudio": None,
        "videoHdUrl": None,
        "videoSdUrl": None,
        "thumbnailUrl": None,
        "captionsUrl": None,
        "captionLocales": [],
        "hasCaptions": False,
        "transcript": None,
        "transcriptSource": None,
    }


# A bare numeric `id` is not enough to call a node a video: a `video_owner` node
# carries the page's numeric id the same way, and treating it as a video invents
# a phantom record keyed by the page. One of these markers has to be present too.
VIDEO_MARKERS = (
    "browser_native_hd_url", "browser_native_sd_url", "captions_url",
    "video_available_captions_locales", "dash_manifest_xml_string",
    "playable_url", "play_count", "play_count_reduced", "playable_duration_in_ms",
    "transcript_urls", "is_video_broadcast",
)


def _which_video(node: dict) -> str | None:
    candidate = node.get("id")
    if (
        isinstance(candidate, str)
        and candidate.isdigit()
        and len(candidate) >= 6
        and any(marker in node for marker in VIDEO_MARKERS)
    ):
        return candidate
    video = node.get("video")
    if isinstance(video, dict) and isinstance(video.get("id"), str) and video["id"].isdigit():
        return video["id"]
    for key in ("shareable_url", "permalink_url", "url"):
        value = node.get(key)
        if isinstance(value, str):
            found = video_id(value)
            if found:
                return found
    return _decode_story_id(node.get("id"))


def collect_videos(payload: Any) -> dict[str, dict]:
    """Two passes: work out which videos exist, then attach everything about them.

    The second pass is what makes titles and owners come through. Those sit on
    nodes whose only link to the video is a bare numeric `id` -- the same shape a
    `video_owner` node has -- so they can only be trusted once the id is already
    known to be a video's.
    """
    known = {
        vid for vid in (_which_video(node) for node in walk(payload)) if vid
    }
    videos: dict[str, dict] = {}

    for node in walk(payload):
        vid = _which_video(node)
        if not vid:
            candidate = node.get("id")
            if isinstance(candidate, str) and candidate in known:
                vid = candidate
        if not vid:
            continue
        entry = videos.setdefault(vid, _blank(vid))

        for key in ("shareable_url", "permalink_url"):
            value = node.get(key)
            if entry["permalinkUrl"] is None and isinstance(value, str) and "facebook.com" in value:
                entry["permalinkUrl"] = value
                entry["isReel"] = "/reel/" in value

        if entry["videoHdUrl"] is None and isinstance(node.get("browser_native_hd_url"), str):
            entry["videoHdUrl"] = node["browser_native_hd_url"]
        if entry["videoSdUrl"] is None and isinstance(node.get("browser_native_sd_url"), str):
            entry["videoSdUrl"] = node["browser_native_sd_url"]

        video = node.get("video")
        if entry["thumbnailUrl"] is None and isinstance(video, dict):
            thumb = video.get("first_frame_thumbnail") or video.get("preferred_thumbnail")
            if isinstance(thumb, str):
                entry["thumbnailUrl"] = thumb
            elif isinstance(thumb, dict) and isinstance(thumb.get("image"), dict):
                entry["thumbnailUrl"] = thumb["image"].get("uri")

        playback = node.get("playback_video")
        if isinstance(playback, dict):
            if entry["lengthSeconds"] is None and isinstance(
                playback.get("length_in_second"), (int, float)
            ):
                entry["lengthSeconds"] = round(float(playback["length_in_second"]), 2)
            entry["width"] = entry["width"] or playback.get("width")
            entry["height"] = entry["height"] or playback.get("height")

        if entry["lengthSeconds"] is None and isinstance(
            node.get("playable_duration_in_ms"), (int, float)
        ):
            entry["lengthSeconds"] = round(node["playable_duration_in_ms"] / 1000.0, 2)

        owner = node.get("video_owner") or node.get("owner")
        if entry["pageName"] is None and isinstance(owner, dict) and owner.get("name"):
            entry["pageName"] = owner.get("name")
            entry["pageId"] = owner.get("id")
            entry["pageUrl"] = owner.get("url")

        if entry["playCountLabel"] is None and isinstance(
            node.get("play_count_reduced"), str
        ):
            entry["playCountLabel"] = node["play_count_reduced"]
            entry["playCount"] = parse_count(node["play_count_reduced"])
        if isinstance(node.get("play_count"), int):
            # An exact count always wins over the abbreviated label.
            entry["playCount"] = node["play_count"]
            entry["playCountLabel"] = entry["playCountLabel"] or str(node["play_count"])

        if entry["trackTitle"] is None and isinstance(node.get("track_title"), str):
            entry["trackTitle"] = node["track_title"]
        if entry["isOriginalAudio"] is None and "is_original_audio_on_facebook" in node:
            entry["isOriginalAudio"] = node.get("is_original_audio_on_facebook")

        if entry["captionsUrl"] is None and isinstance(node.get("captions_url"), str):
            entry["captionsUrl"] = node["captions_url"]
            entry["hasCaptions"] = True
        locales = node.get("video_available_captions_locales")
        if isinstance(locales, list) and locales and not entry["captionLocales"]:
            entry["captionLocales"] = [
                {
                    "creationMethod": loc.get("localized_creation_method"),
                    "captionsUrl": loc.get("captions_url"),
                }
                for loc in locales
                if isinstance(loc, dict)
            ]

        if entry["postId"] is None and isinstance(node.get("post_id"), str):
            entry["postId"] = node["post_id"]
        if entry["createdAt"] is None and isinstance(node.get("creation_time"), int):
            entry["createdAt"] = node["creation_time"]

        message = node.get("message")
        if entry["caption"] is None and isinstance(message, dict):
            text = message.get("text")
            if isinstance(text, str) and text.strip():
                entry["caption"] = text
        title = node.get("title")
        if entry["title"] is None and isinstance(title, dict):
            text = title.get("text")
            if isinstance(text, str) and text.strip():
                entry["title"] = text

        if entry["reactionCount"] is None and "i18n_reaction_count" in node:
            entry["reactionCount"] = _int(node.get("i18n_reaction_count"))
        if entry["commentCount"] is None and "total_comment_count" in node:
            entry["commentCount"] = _int(node.get("total_comment_count"))
        if entry["commentCount"] is None and isinstance(node.get("comments"), dict):
            entry["commentCount"] = _int(node["comments"].get("total_count"))
        if entry["shareCount"] is None and "share_count" in node:
            entry["shareCount"] = _int(node.get("share_count"))

    for entry in videos.values():
        entry["createdAtIso"] = _iso(entry["createdAt"])
        if entry["permalinkUrl"] is None:
            entry["permalinkUrl"] = f"https://www.facebook.com/watch/?v={entry['videoId']}"
        entry["hasCaptions"] = bool(entry["captionsUrl"] or entry["captionLocales"])
        _engagement(entry)
    return videos


def _engagement(entry: dict) -> None:
    """Total engagement, and engagement rate against plays where both are known.

    The rate is left null when the play count is unknown or zero rather than
    being computed against a placeholder -- a fabricated denominator here would
    turn an unknown into a confident wrong number.
    """
    parts = [entry.get(k) for k in ("reactionCount", "commentCount", "shareCount")]
    known = [p for p in parts if isinstance(p, int)]
    entry["engagementTotal"] = sum(known) if known else None
    plays = entry.get("playCount")
    if entry["engagementTotal"] is not None and isinstance(plays, int) and plays > 0:
        entry["engagementRatePercent"] = round(100.0 * entry["engagementTotal"] / plays, 3)
    else:
        entry["engagementRatePercent"] = None


def parse_html(html: str) -> list[dict]:
    """Every video in a rendered tab or permalink page."""
    merged: dict[str, dict] = {}
    for block in iter_json_blocks(html):
        for vid, entry in collect_videos(block).items():
            target = merged.setdefault(vid, _blank(vid))
            for key, value in entry.items():
                if target.get(key) in (None, [], False) and value not in (None, [], False):
                    target[key] = value
    for entry in merged.values():
        entry["hasCaptions"] = bool(entry["captionsUrl"] or entry["captionLocales"])
        _engagement(entry)
    return [v for v in merged.values() if v["videoHdUrl"] or v["playCount"] is not None
            or v["createdAt"] or v["caption"]]


def parse_srt(text: str) -> tuple[str, list[dict]]:
    """Turn a Facebook .srt caption file into plain text plus timed cues."""
    cues = []
    for _, start, end, body in SRT_BLOCK.findall(text or ""):
        line = " ".join(part.strip() for part in body.strip().splitlines() if part.strip())
        if line:
            cues.append({"start": start, "end": end, "text": line})
    transcript = " ".join(cue["text"] for cue in cues)
    return transcript, cues


def matches_filters(video: dict, filters: dict) -> bool:
    if filters.get("onlyReels") and not video.get("isReel"):
        return False
    if filters.get("onlyWithCaptions") and not video.get("hasCaptions"):
        return False
    minimum = filters.get("minPlays")
    if isinstance(minimum, int):
        plays = video.get("playCount")
        # An unknown play count cannot be shown to clear the bar.
        if not isinstance(plays, int) or plays < minimum:
            return False
    needle = (filters.get("captionContains") or "").strip().lower()
    if needle:
        haystack = " ".join(
            str(video.get(field) or "")
            for field in ("caption", "title", "transcript")
        ).lower()
        if needle not in haystack:
            return False
    return True


def summarise(videos: Iterable[dict]) -> dict:
    videos = list(videos)
    plays = [v["playCount"] for v in videos if isinstance(v.get("playCount"), int)]
    rates = [v["engagementRatePercent"] for v in videos
             if isinstance(v.get("engagementRatePercent"), float)]
    lengths = [v["lengthSeconds"] for v in videos if isinstance(v.get("lengthSeconds"), float)]
    return {
        "videosCollected": len(videos),
        "reels": sum(1 for v in videos if v.get("isReel")),
        "withCaptions": sum(1 for v in videos if v.get("hasCaptions")),
        "withTranscript": sum(1 for v in videos if v.get("transcript")),
        "withDownloadUrl": sum(1 for v in videos if v.get("videoHdUrl") or v.get("videoSdUrl")),
        "totalPlays": sum(plays) if plays else None,
        "medianPlays": sorted(plays)[len(plays) // 2] if plays else None,
        "medianEngagementRatePercent": (
            round(sorted(rates)[len(rates) // 2], 3) if rates else None
        ),
        "medianLengthSeconds": sorted(lengths)[len(lengths) // 2] if lengths else None,
        "pages": len(dedupe([v.get("pageName") for v in videos if v.get("pageName")])),
    }
