"""Per-surface scrape logic: one coroutine per mode.

Each mode is a single embed request, parsed into rows. Where a surface has a
ceiling -- a hashtag page shipping six videos, a profile embed publishing no
video list -- the mode records it in the row's `_warning` instead of looping
pointlessly or implying the first page is everything.
"""

from __future__ import annotations

import logging
import re

from src.client import NotFoundError, TikTokClient
from src.constants import (
    EMBED_HASHTAG,
    EMBED_MUSIC,
    EMBED_USER,
    EMBED_VIDEO,
    ERR_EMPTY,
    ERR_PRIVATE,
    MODE_HASHTAG,
    MODE_MUSIC,
    MODE_OEMBED,
    MODE_PROFILE,
    MODE_VIDEO,
    OEMBED_URL,
    SOURCE_EMBED,
    SOURCE_OEMBED,
    WARN_LIST_ITEM_FIELDS,
    WARN_NO_VIDEO_LIST,
    WARN_ROUNDED_PLAYCOUNT,
    WARN_SINGLE_PAGE,
)
from src.extract import (
    SHORT_LINK_RE,
    normalise_oembed,
    normalise_playlist_info,
    normalise_playlist_item,
    normalise_profile,
    normalise_video,
    now_iso,
)
from src.state import ShapeError, assert_found, parse_state, route_payload

logger = logging.getLogger(__name__)


def envelope(mode: str, target: str, source: str, **extra) -> dict:
    """The fields every row carries, whatever the mode."""
    row = {
        "_mode": mode,
        "_input": target,
        "_source": source,
        "_scrapedAt": now_iso(),
        "_index": None,
        "_warning": None,
        "_error": None,
        "_errorDetail": None,
    }
    row.update(extra)
    return row


async def _payload(client: TikTokClient, url: str, what: str) -> dict:
    """Fetch an embed page and return its route payload.

    `LookupError` from `assert_found` is translated to `NotFoundError` so callers
    handle one missing-entity exception type rather than two.
    """
    html = await client.get_embed_html(url)
    payload = route_payload(parse_state(html))
    try:
        assert_found(payload, what)
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    return payload


async def scrape_profile(client: TikTokClient, target: str, options: dict) -> list[dict]:
    """Account stats from `/embed/@<username>`.

    One row. The embed publishes no video list, so the warning says so rather
    than leaving a caller to wonder where the posts went.
    """
    payload = await _payload(client, EMBED_USER.format(username=target), f"@{target}")
    user = payload.get("userInfo")
    if not isinstance(user, dict) or not user.get("uniqueId"):
        raise ShapeError(
            "profile embed carried no userInfo object; payload keys were "
            + ", ".join(sorted(payload)[:8])
        )
    row = normalise_profile(user)
    warning = WARN_NO_VIDEO_LIST
    error = None
    if user.get("privateAccount"):
        error = ERR_PRIVATE
    return [envelope(
        MODE_PROFILE, target, SOURCE_EMBED,
        _warning=warning, _error=error, **row,
    )]


async def scrape_video(client: TikTokClient, target: str, options: dict) -> list[dict]:
    """Full engagement for one video from `/embed/v2/<videoId>`.

    A `vm.tiktok.com` short link arrives here unresolved (it cannot be parsed
    offline), so it costs one extra redirect-following request.
    """
    video_id = target
    resolved_from = None
    if SHORT_LINK_RE.match(target):
        canonical = await client.resolve_redirect(target)
        resolved_from = target
        match = re.search(r"/(?:video|photo)/(\d{6,})", canonical)
        if not match:
            raise NotFoundError(f"{target} resolved to {canonical} with no video id")
        video_id = match.group(1)

    payload = await _payload(client, EMBED_VIDEO.format(video_id=video_id), f"video {video_id}")
    video_data = payload.get("videoData")
    if not isinstance(video_data, dict) or not (video_data.get("itemInfos") or {}).get("id"):
        raise ShapeError(
            "video embed carried no videoData.itemInfos.id; payload keys were "
            + ", ".join(sorted(payload)[:8])
        )
    row = normalise_video(video_data)
    return [envelope(
        MODE_VIDEO, resolved_from or target, SOURCE_EMBED,
        _warning=WARN_ROUNDED_PLAYCOUNT, **row,
    )]


async def _scrape_playlist(
    client: TikTokClient, target: str, options: dict, mode: str, url: str, what: str
) -> list[dict]:
    """Shared body for the hashtag and music modes -- identical payload shape."""
    payload = await _payload(client, url, what)
    items = payload.get("videoList")
    info = payload.get("embedInfo") or {}
    playlist_type = payload.get("playlistType")
    if not isinstance(items, list):
        raise ShapeError(
            f"{mode} embed carried no videoList array; payload keys were "
            + ", ".join(sorted(payload)[:8])
        )

    shared = normalise_playlist_info(info, playlist_type)
    warning = f"{WARN_SINGLE_PAGE};{WARN_LIST_ITEM_FIELDS}"

    if not items:
        return [envelope(
            mode, target, SOURCE_EMBED,
            _warning=warning, _error=ERR_EMPTY,
            _errorDetail=f"{what} exists but its embed shipped an empty videoList",
            **shared,
        )]

    max_items = options.get("maxItems") or len(items)
    rows = []
    for index, item in enumerate(items[:max_items], start=1):
        if not isinstance(item, dict):
            continue
        rows.append(envelope(
            mode, target, SOURCE_EMBED,
            _index=index, _warning=warning,
            **shared, **normalise_playlist_item(item),
        ))
    return rows


async def scrape_hashtag(client: TikTokClient, target: str, options: dict) -> list[dict]:
    """Videos currently shown on `/embed/tag/<hashtag>` (one page, ~6 rows)."""
    return await _scrape_playlist(
        client, target, options, MODE_HASHTAG,
        EMBED_HASHTAG.format(hashtag=target), f"#{target}",
    )


async def scrape_music(client: TikTokClient, target: str, options: dict) -> list[dict]:
    """Videos currently shown on `/embed/music/<musicId>` (one page, ~9 rows)."""
    return await _scrape_playlist(
        client, target, options, MODE_MUSIC,
        EMBED_MUSIC.format(music_id=target), f"music {target}",
    )


async def scrape_oembed(client: TikTokClient, target: str, options: dict) -> list[dict]:
    """TikTok's official oEmbed record for a video url.

    Cheaper and more stable than the embed page (1.3 KB against 302 KB) but it
    carries no engagement counters -- use it to validate urls in bulk or to fetch
    thumbnails, and `video` mode when the numbers matter.
    """
    from urllib.parse import quote

    url = f"{OEMBED_URL}?url={quote(target, safe='')}"
    payload = await client.get_oembed(url, target)
    row = normalise_oembed(payload)
    if not row.get("videoId") and not row.get("title"):
        raise ShapeError(
            "oEmbed returned an object with neither embed_product_id nor title; keys were "
            + ", ".join(sorted(payload)[:8])
        )
    return [envelope(MODE_OEMBED, target, SOURCE_OEMBED, **row)]


SCRAPERS = {
    MODE_PROFILE: scrape_profile,
    MODE_VIDEO: scrape_video,
    MODE_HASHTAG: scrape_hashtag,
    MODE_MUSIC: scrape_music,
    MODE_OEMBED: scrape_oembed,
}
