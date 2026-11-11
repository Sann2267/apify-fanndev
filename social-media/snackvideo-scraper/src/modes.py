"""One async generator per mode. Each yields finished records for one target.

Pagination rules, all measured in recon (2026-09-25):
  profile  /pc/feed/profile  pcursor <- response.cursor, ends at "no_more".
           Walked a 357-video account to exactly ownerCount.photo_public.
  hashtag  /pic/topic        pcursor <- response.pcursor (an offset). A real
           index: deterministic, relevant, gibberish -> 0 items. Went 3,600+
           deep without ending; ~5% of each page repeats earlier items.
  playlist /pwa/feed/album   pcursor <- response.cursor, ends at "no_more".
  search   /pwa/v2/search/word/outer  NOT an index: a keyword-biased
           recommendation feed. pcursor is ignored, the same query twice
           shares 0/20 items and gibberish still returns 20 fillers. We sample
           until maxItems or it stops adding new items, and flag each record
           with keywordMatched.
  trending /pwa/feed/slides  the For You feed; every call is a fresh sample.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from .client import SnackApiError, SnackClient, SnackNotFound
from .constants import (
    EP_ALBUM,
    EP_PROFILE,
    EP_PROFILE_FEED,
    EP_SEARCH,
    EP_SLIDES,
    EP_TOPIC,
    MAX_PAGES_PER_TARGET,
    PAGE_ALBUM,
    PAGE_PROFILE_FEED,
    PAGE_SEARCH,
    PAGE_SLIDES,
    PAGE_TOPIC,
    SITE,
    STALL_PAGES,
)
from .parsers import (
    encode_uri_component,
    error_record,
    is_snack_url,
    is_url,
    keyword_matches,
    parse_handle,
    parse_hashtag,
    parse_playlist_id,
    parse_video_id,
    playlist_record,
    profile_record,
    slug_word,
    video_record,
)

log = logging.getLogger("snackvideo.modes")

Record = dict[str, Any]


@dataclass
class Options:
    max_items: int
    include_videos: bool
    include_playlists: bool
    include_manifest: bool
    only_keyword_matches: bool


async def _resolve(client: SnackClient, value: str, parse) -> str | None:
    """Parse directly; for foreign/short share links follow redirects first."""
    parsed = parse(value)
    if parsed is None and is_url(value) and not is_snack_url(value):
        final = await client.get_final_url(value)
        log.info("Share link %s -> %s", value, final)
        parsed = parse(final)
    return parsed


async def _walk(
    client: SnackClient,
    path: str,
    make_body,
    next_cursor,
    first_cursor: Any,
    limit: int,
) -> AsyncIterator[tuple[int, dict[str, Any], list[dict[str, Any]]]]:
    """Generic cursor walk. Yields (page_no, raw_response, new_unique_feeds).

    Stops on: cursor exhausted ('no_more'/empty), limit reached, STALL_PAGES
    pages in a row with nothing new, or MAX_PAGES_PER_TARGET.
    """
    seen: set[str] = set()
    cursor = first_cursor
    stalled = 0
    for page in range(MAX_PAGES_PER_TARGET):
        data = await client.api(path, make_body(cursor))
        feeds = data.get("feeds") or []
        fresh = []
        for f in feeds:
            pid = str(f.get("photo_id_str") or f.get("photo_id") or "")
            if pid and pid not in seen:
                seen.add(pid)
                fresh.append(f)
        yield page, data, fresh
        if len(seen) >= limit:
            return
        stalled = stalled + 1 if not fresh else 0
        if stalled >= STALL_PAGES:
            log.info("%s: %d pages in a row added nothing new - stopping at %d items", path, stalled, len(seen))
            return
        cursor = next_cursor(data)
        if cursor in (None, "", "no_more"):
            return


# -- profile ---------------------------------------------------------------

async def run_profile(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    handle = await _resolve(client, value, parse_handle)
    if not handle:
        yield error_record(value, "invalid_input", "Expected @handle, handle or a snackvideo.com/@handle URL")
        return
    data = await client.api(EP_PROFILE, {"userId": handle, "mcc": "", "deviceId": "", "fromPhoto": False})
    # A missing account is NOT an error code: it is result=1 with no
    # userProfile at all (hollow 200).
    if not isinstance(data.get("userProfile"), dict) or not (data["userProfile"].get("profile") or {}).get("kwai_id"):
        yield error_record(value, "not_found", f"No public SnackVideo profile for @{handle}")
        return
    yield profile_record(data, input_value=value)

    if not (opt.include_videos or opt.include_playlists):
        return
    kwai_id = data["userProfile"]["profile"]["kwai_id"]
    limit = opt.max_items if opt.include_videos else 1
    emitted = 0
    async for page, raw, fresh in _walk(
        client,
        EP_PROFILE_FEED,
        lambda cur: {"userId": kwai_id, "fromPage": "PC_PROFILE", "beforePage": "", "pcursor": cur,
                     "count": min(PAGE_PROFILE_FEED, max(limit, 1))},
        lambda d: d.get("cursor"),
        "",
        limit,
    ):
        if page == 0 and opt.include_playlists:
            # Playlists ride on the first feed page only (up to 20 of them;
            # later pages carry none - see README limits).
            for album in raw.get("albums") or []:
                yield playlist_record(album, input_value=value, source="S1-api-profile-feed", kwai_id=kwai_id)
        if not opt.include_videos:
            return
        for f in fresh:
            if emitted >= opt.max_items:
                return
            emitted += 1
            yield video_record(f, input_value=value, source="S1-api-profile-feed",
                               include_manifest=opt.include_manifest)


# -- single video ----------------------------------------------------------

async def run_video(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    photo_id = await _resolve(client, value, parse_video_id)
    if not photo_id:
        yield error_record(value, "invalid_input", "Expected a snackvideo.com video URL, a share link or a numeric video ID")
        return
    try:
        data = await client.api(EP_SLIDES, {"photo_id_str": photo_id, "count": 3, "request_source": 1105, "mobile": True})
    except SnackNotFound:
        yield error_record(value, "not_found", f"Video {photo_id} does not exist or was removed")
        return
    # The endpoint returns the requested video first, then related ones.
    feed = next((f for f in data.get("feeds") or [] if str(f.get("photo_id_str")) == photo_id), None)
    if feed is None:
        yield error_record(value, "not_found", f"Video {photo_id} was not in the response")
        return
    yield video_record(feed, input_value=value, source="S1-api-slides", include_manifest=opt.include_manifest)


# -- hashtag (topic) -------------------------------------------------------

async def run_hashtag(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    tag = parse_hashtag(value)
    if not tag:
        yield error_record(value, "invalid_input", "Expected a hashtag like 'kucing' / '#kucing' or a /topic/ URL")
        return
    topic = encode_uri_component(slug_word(tag))
    emitted = 0
    async for page, _raw, fresh in _walk(
        client,
        EP_TOPIC,
        lambda cur: {"topic": topic, "pcursor": cur, "count": min(PAGE_TOPIC, opt.max_items)},
        lambda d: d.get("pcursor"),
        0,
        opt.max_items,
    ):
        if page == 0 and not fresh:
            yield error_record(value, "no_results", f"Hashtag #{tag} has no public videos")
            return
        for f in fresh:
            if emitted >= opt.max_items:
                return
            emitted += 1
            yield video_record(f, input_value=value, source="S1-api-topic",
                               include_manifest=opt.include_manifest, extra={"hashtag": tag})


# -- keyword search --------------------------------------------------------

async def run_search(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    keyword = value.strip()
    if not keyword:
        return
    word = encode_uri_component(slug_word(keyword))
    body = {
        "ai_content": False, "need_ld_json": False, "need_tdk": False,
        "searchWord": word, "pcursor": 0, "count": min(PAGE_SEARCH, opt.max_items),
        "mobile": True, "request_source": 1102, "fromUser": False,
        "seoDefaultFilterV2": True, "url": f"{SITE}/discover/{word}",
    }
    emitted = matched = 0
    page_no = 0
    async for page, _raw, fresh in _walk(
        client, EP_SEARCH,
        lambda cur: dict(body, pcursor=cur),
        lambda d: page_no + 1,  # ignored upstream; sent to mirror the web app
        0,
        # When filtering, the dedupe budget must exceed maxItems: most sampled
        # items will not match.
        opt.max_items * (10 if opt.only_keyword_matches else 1),
    ):
        page_no = page
        page_matches = 0
        for f in fresh:
            hit = keyword_matches(keyword, f.get("caption"))
            if opt.only_keyword_matches and not hit:
                continue
            if emitted >= opt.max_items:
                return
            emitted += 1
            matched += hit
            page_matches += hit
            yield video_record(f, input_value=value, source="S1-api-search",
                               include_manifest=opt.include_manifest,
                               extra={"searchKeyword": keyword, "keywordMatched": hit})
        if emitted >= opt.max_items:
            return
    log.info("Search %r: %d videos, %d with the keyword in the caption", keyword, emitted, matched)


# -- trending (For You) ----------------------------------------------------

async def run_trending(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    emitted = 0
    async for _page, _raw, fresh in _walk(
        client, EP_SLIDES,
        lambda cur: {"count": min(PAGE_SLIDES, opt.max_items), "request_source": 1105, "mobile": True},
        lambda d: "next",  # every call is a fresh sample; no cursor exists
        None,
        opt.max_items,
    ):
        for f in fresh:
            if emitted >= opt.max_items:
                return
            emitted += 1
            yield video_record(f, input_value=value, source="S1-api-foryou",
                               include_manifest=opt.include_manifest, extra={"feedRank": emitted})


# -- playlist (album) ------------------------------------------------------

async def run_playlist(client: SnackClient, value: str, opt: Options) -> AsyncIterator[Record]:
    album_id = await _resolve(client, value, parse_playlist_id)
    if not album_id:
        yield error_record(value, "invalid_input", "Expected a snackvideo.com/@user/playlist/<id> URL or a numeric playlist ID")
        return
    emitted = 0
    try:
        async for page, raw, fresh in _walk(
            client, EP_ALBUM,
            lambda cur: {"albumId": album_id, "pcursor": cur, "count": PAGE_ALBUM},
            lambda d: d.get("cursor"),
            "",
            opt.max_items,
        ):
            if page == 0:
                album = raw.get("album")
                if not isinstance(album, dict) or not (album.get("albumIdStr") or album.get("albumId")):
                    yield error_record(value, "not_found", f"Playlist {album_id} does not exist or is private")
                    return
                kwai_id = next((f.get("kwai_id") for f in raw.get("feeds") or [] if f.get("kwai_id")), None)
                yield playlist_record(album, input_value=value, source="S1-api-album", kwai_id=kwai_id)
            for f in fresh:
                if emitted >= opt.max_items:
                    return
                emitted += 1
                yield video_record(f, input_value=value, source="S1-api-album",
                                   include_manifest=opt.include_manifest,
                                   extra={"playlistId": album_id, "playlistPosition": emitted})
    except SnackApiError as exc:
        yield error_record(value, "not_found", f"Playlist {album_id}: {exc}")


MODES = {
    "profile": (run_profile, "usernames"),
    "video": (run_video, "videoUrls"),
    "hashtag": (run_hashtag, "hashtags"),
    "search": (run_search, "searchKeywords"),
    "trending": (run_trending, None),
    "playlist": (run_playlist, "playlistUrls"),
}
