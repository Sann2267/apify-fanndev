"""Fetching reels and videos from a page, and transcripts from Facebook's captions.

Three entry points, all server-rendered:

- `/{slug}/reels/` -- ~13 MB, ten reels with play counts, audio track, direct
  MP4 URLs and, where Facebook has captioned them, a `.srt` URL.
- `/{slug}/videos`  -- ~940 KB, the videos tab, with exact `play_count` integers
  rather than the reels tab's abbreviated `"292K"`.
- `/watch/?v=<id>` -- redirects to the canonical `/{page}/videos/<id>/`, which
  makes it a universal resolver for a bare video id.

The transcript is real, not inferred: `captions_url` is a signed CDN link to an
actual SubRip file, and fetching it returns the spoken text with timings.
"""

from __future__ import annotations

from typing import Any

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders, is_hollow
from src.parser import parse_html, parse_srt

BASE = "https://www.facebook.com/"
REELS_PAGINATION = "ProfileCometAppCollectionReelsRendererPaginationQuery"
VIDEOS_PAGINATION = "PagesCometChannelTabAllVideosCardImplPaginationQuery"


class PageUnavailable(RuntimeError):
    """The page does not exist, or has no reels/videos tab."""


async def fetch_tab(
    session: FacebookSession,
    slug: str,
    tab: str,
    max_videos: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    """One page's reels or videos tab, with pagination where Facebook allows it."""
    path = "reels/" if tab == "reels" else "videos"
    url = f"{BASE}{slug}/{path}"
    html = await session.get_html(url)
    if is_hollow(html):
        raise PageUnavailable(
            "Facebook served the empty shell (~330 KB). No page resolves to this slug."
        )

    videos = parse_html(html)
    meta = {"tabUrl": url, "requestsMade": 1, "paginated": False}
    if not videos:
        raise PageUnavailable(
            f"The {tab} tab rendered but carried no videos. The page may simply "
            f"have none, or may not publish a {tab} tab."
        )
    if len(videos) >= max_videos:
        return videos[:max_videos], meta

    query_name = REELS_PAGINATION if tab == "reels" else VIDEOS_PAGINATION
    doc_id = await session.bundle_doc_id(html, query_name)
    cursor = _cursor(html)
    preloaders = harvest_preloaders(html)
    base_vars: dict[str, Any] = {}
    for _, (_, variables) in preloaders.items():
        if len(variables) > len(base_vars):
            base_vars = variables

    if not doc_id or not cursor or not base_vars:
        # The rendered tab is still a complete answer for what it carried.
        meta["paginationUnavailable"] = True
        return videos[:max_videos], meta

    meta["paginated"] = True
    seen = {v["videoId"] for v in videos}
    while len(videos) < max_videos and cursor:
        variables = dict(base_vars)
        variables["cursor"] = cursor
        variables["count"] = 8
        try:
            payload = await session.graphql(html, query_name, doc_id, variables, referer=url)
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        meta["requestsMade"] += 1

        batch = parse_html_payload(payload)
        fresh = [v for v in batch if v["videoId"] not in seen]
        if not fresh:
            break
        for video in fresh:
            seen.add(video["videoId"])
        videos.extend(fresh)
        if log:
            log.info(f"  +{len(fresh)} video(s) (running total {len(videos)})")
        cursor = _cursor_from_payload(payload)

    return videos[:max_videos], meta


def parse_html_payload(payload: Any) -> list[dict]:
    from src.parser import _engagement, collect_videos

    videos = collect_videos(payload)
    for entry in videos.values():
        entry["hasCaptions"] = bool(entry["captionsUrl"] or entry["captionLocales"])
        _engagement(entry)
    return [v for v in videos.values()
            if v["videoHdUrl"] or v["playCount"] is not None or v["createdAt"]]


def _cursor(html: str) -> str | None:
    from src.fbcore import iter_json_blocks, walk

    for block in iter_json_blocks(html):
        for node in walk(block):
            info = node.get("page_info")
            if isinstance(info, dict) and info.get("end_cursor"):
                return info["end_cursor"]
    return None


def _cursor_from_payload(payload: Any) -> str | None:
    from src.fbcore import walk

    for node in walk(payload):
        info = node.get("page_info")
        if isinstance(info, dict) and info.get("end_cursor") and info.get("has_next_page"):
            return info["end_cursor"]
    return None


async def fetch_single(session: FacebookSession, vid: str) -> dict:
    """One video or reel by id.

    `/watch/?v=<id>` is used as the entry point because it redirects to whichever
    canonical URL the video actually lives at -- a reel or a page video -- so the
    caller does not have to know which it is.
    """
    url = f"{BASE}watch/?v={vid}"
    html = await session.get_html(url)
    if is_hollow(html):
        raise PageUnavailable(
            "Facebook served the empty shell (~330 KB). No video resolves to this id."
        )
    videos = parse_html(html)
    for video in videos:
        if video["videoId"] == vid:
            return video
    if videos:
        # The watch URL can land on a canonical page that carries related videos
        # too; returning one of those instead of the requested id would be wrong.
        raise PageUnavailable(
            f"The page rendered but carried no data for video {vid}. It may have "
            "been removed, or be restricted to logged-in viewers."
        )
    raise PageUnavailable(f"No video data found for {vid}.")


async def add_transcript(session: FacebookSession, video: dict) -> None:
    """Download and parse the caption file, when Facebook published one."""
    url = video.get("captionsUrl")
    if not url:
        for locale in video.get("captionLocales") or []:
            if locale.get("captionsUrl"):
                url = locale["captionsUrl"]
                video["transcriptSource"] = locale.get("creationMethod")
                break
    if not url:
        return
    try:
        response = await session._session.get(url, headers={"accept": "*/*"})
    except Exception:
        return
    if response.status_code != 200:
        return
    transcript, cues = parse_srt(response.text)
    if transcript:
        video["transcript"] = transcript
        video["transcriptCues"] = cues
        video["transcriptSource"] = video.get("transcriptSource") or "facebook-captions"
