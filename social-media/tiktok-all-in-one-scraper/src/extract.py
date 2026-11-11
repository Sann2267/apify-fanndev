"""Input parsing and row normalisation.

Input parsing is deliberately generous -- people paste whatever they have: a
bare handle, an `@handle`, a full profile url, a share url with a tracking query
string, a short `vm.tiktok.com` link, a hashtag with or without `#`, a music url
whose slug ends in the id. Anything that cannot be resolved becomes an
`INVALID_INPUT` row rather than a silent skip.

Normalisation flattens TikTok's nested embed payloads into one row per entity,
keeping the raw counter names recognisable (`diggCount` stays `diggCount`) so a
reader who knows the platform does not have to learn a new vocabulary.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.state import first_int, first_url


class InvalidInput(Exception):
    """The entry could not be resolved into a target for this mode."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Input parsers
# ---------------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,24}$")
_VIDEO_URL_RE = re.compile(r"/video/(\d{6,})")
_PHOTO_URL_RE = re.compile(r"/photo/(\d{6,})")
_TRAILING_ID_RE = re.compile(r"(\d{6,})\s*$")
SHORT_LINK_RE = re.compile(r"https?://(?:vm|vt)\.tiktok\.com/\S+", re.I)


def _strip(text: str) -> str:
    return (text or "").strip()


def parse_username(text: str) -> str:
    """`nasa`, `@nasa`, `https://www.tiktok.com/@nasa?lang=en` -> `nasa`."""
    raw = _strip(text)
    if not raw:
        raise InvalidInput("empty entry")
    if "tiktok.com" in raw.lower():
        match = re.search(r"/@([A-Za-z0-9._]{1,24})", raw)
        if not match:
            raise InvalidInput(f"no @username in url {raw!r}")
        handle = match.group(1)
    else:
        handle = raw.lstrip("@").split("?", 1)[0].strip("/")
    if not _USERNAME_RE.match(handle):
        raise InvalidInput(f"{handle!r} is not a valid TikTok username")
    return handle


def parse_video_id(text: str) -> str:
    """A video/photo url or a bare numeric id -> the id.

    Short `vm.tiktok.com` links cannot be resolved without a request, so they are
    returned verbatim and the mode resolves them (see `modes.scrape_video`).
    """
    raw = _strip(text)
    if not raw:
        raise InvalidInput("empty entry")
    if SHORT_LINK_RE.match(raw):
        return raw
    for pattern in (_VIDEO_URL_RE, _PHOTO_URL_RE):
        match = pattern.search(raw)
        if match:
            return match.group(1)
    if raw.isdigit() and len(raw) >= 6:
        return raw
    raise InvalidInput(
        f"{raw!r} is not a video url, photo url, short link or numeric video id"
    )


def parse_hashtag(text: str) -> str:
    """`#fyp`, `fyp`, `https://www.tiktok.com/tag/fyp` -> `fyp`."""
    raw = _strip(text)
    if not raw:
        raise InvalidInput("empty entry")
    if "tiktok.com" in raw.lower():
        match = re.search(r"/tag/([^/?#]+)", raw)
        if not match:
            raise InvalidInput(f"no /tag/ segment in url {raw!r}")
        tag = match.group(1)
    else:
        tag = raw.lstrip("#").split("?", 1)[0].strip("/")
    tag = tag.strip()
    if not tag or "/" in tag:
        raise InvalidInput(f"{raw!r} is not a usable hashtag")
    return tag


def parse_music_id(text: str) -> str:
    """`https://www.tiktok.com/music/euphoria-7301919715965077506` -> the id."""
    raw = _strip(text)
    if not raw:
        raise InvalidInput("empty entry")
    if raw.isdigit() and len(raw) >= 6:
        return raw
    match = _TRAILING_ID_RE.search(raw.split("?", 1)[0].rstrip("/"))
    if match:
        return match.group(1)
    raise InvalidInput(
        f"{raw!r} carries no music id -- paste the music url (its slug ends in the "
        "id) or the bare id"
    )


def parse_video_url(text: str) -> str:
    """For oEmbed, which takes the url rather than the id."""
    raw = _strip(text)
    if not raw:
        raise InvalidInput("empty entry")
    if raw.startswith("http"):
        return raw
    if raw.isdigit() and len(raw) >= 6:
        # oEmbed accepts the canonical form with any handle in it.
        raise InvalidInput(
            "oembed mode needs the full video url, not a bare id (TikTok's oEmbed "
            "endpoint will not accept a url without the @handle)"
        )
    raise InvalidInput(f"{raw!r} is not a url")


# ---------------------------------------------------------------------------
# Row normalisers
# ---------------------------------------------------------------------------

def normalise_profile(user: dict) -> dict:
    """`userInfo` from `/embed/@<user>`."""
    return {
        "userId": str(user.get("id")) if user.get("id") is not None else None,
        "uniqueId": user.get("uniqueId"),
        "nickname": user.get("nickname"),
        "signature": user.get("signature"),
        "verified": user.get("verified"),
        "privateAccount": user.get("privateAccount"),
        "followerCount": first_int(user.get("followerCount")),
        "followingCount": first_int(user.get("followingCount")),
        "heartCount": first_int(user.get("heartCount")),
        "avatarUrl": first_url(user.get("avatarThumbUrl")),
        "profileUrl": (
            f"https://www.tiktok.com/@{user.get('uniqueId')}"
            if user.get("uniqueId") else None
        ),
    }


def normalise_video(video_data: dict) -> dict:
    """`videoData` from `/embed/v2/<id>`: item + author + author stats + music."""
    item = video_data.get("itemInfos") or {}
    author = video_data.get("authorInfos") or {}
    stats = video_data.get("authorStats") or {}
    music = video_data.get("musicInfos") or {}
    meta = item.get("videoMeta") or {}
    challenges = video_data.get("challengeInfoList") or []
    image_post = video_data.get("imagePostInfo")

    created = first_int(item.get("createTime"))
    return {
        "videoId": str(item.get("id")) if item.get("id") is not None else None,
        "description": item.get("text"),
        "createTime": created,
        "createTimeIso": (
            datetime.fromtimestamp(created, timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z")
            if created else None
        ),
        "diggCount": first_int(item.get("diggCount")),
        "commentCount": first_int(item.get("commentCount")),
        "shareCount": first_int(item.get("shareCount")),
        "playCount": first_int(item.get("playCount")),
        "videoWidth": first_int(meta.get("width")),
        "videoHeight": first_int(meta.get("height")),
        "videoDuration": first_int(meta.get("duration")),
        "isAd": item.get("isAd"),
        "isOriginal": item.get("isOriginal"),
        "isOfficial": item.get("isOfficial"),
        "isEcommerceVideo": bool(item.get("isECVideo")),
        "brandOrganicType": item.get("brandOrganicType") or None,
        "locationCreated": item.get("locationCreated"),
        "isPhotoPost": image_post is not None,
        "coverUrl": first_url(item.get("covers")),
        "dynamicCoverUrl": first_url(item.get("coversDynamic")),
        "hashtags": [
            c.get("challengeName") or c.get("title")
            for c in challenges
            if isinstance(c, dict) and (c.get("challengeName") or c.get("title"))
        ] or None,
        "authorUserId": str(author.get("userId")) if author.get("userId") else None,
        "authorSecUid": author.get("secUid"),
        "authorUniqueId": author.get("uniqueId"),
        "authorNickname": author.get("nickName"),
        "authorSignature": author.get("signature"),
        "authorVerified": author.get("verified"),
        "authorAvatarUrl": first_url(author.get("coversMedium") or author.get("covers")),
        "authorFollowerCount": first_int(stats.get("followerCount")),
        "authorFollowingCount": first_int(stats.get("followingCount")),
        "authorHeartCount": first_int(stats.get("heartCount")),
        "authorVideoCount": first_int(stats.get("videoCount")),
        "musicId": str(music.get("musicId")) if music.get("musicId") else None,
        "musicName": music.get("musicName"),
        "musicAuthorName": music.get("authorName"),
        "musicPlayUrl": first_url(music.get("playUrl")),
        "videoUrl": (
            f"https://www.tiktok.com/@{author.get('uniqueId')}/video/{item.get('id')}"
            if author.get("uniqueId") and item.get("id") else None
        ),
    }


def normalise_playlist_item(item: dict) -> dict:
    """One row of `videoList` from a hashtag or music embed.

    These rows are thinner than `/embed/v2/<id>` on purpose: TikTok only ships
    `playCount` here, with no digg/comment/share counters. Feed the ids back in
    through `video` mode when the full engagement set is needed.
    """
    return {
        "videoId": str(item.get("id")) if item.get("id") is not None else None,
        "description": item.get("desc"),
        "playCount": first_int(item.get("playCount")),
        "videoWidth": first_int(item.get("width")),
        "videoHeight": first_int(item.get("height")),
        "videoRatio": item.get("ratio"),
        "coverUrl": first_url(item.get("coverUrl")),
        "originCoverUrl": first_url(item.get("originCoverUrl")),
        "dynamicCoverUrl": first_url(item.get("dynamicCoverUrl")),
        "playAddr": first_url(item.get("playAddr")),
        "isPrivateItem": item.get("privateItem"),
        "authorUniqueId": item.get("authorUniqueId"),
        "videoUrl": (
            f"https://www.tiktok.com/@{item.get('authorUniqueId')}/video/{item.get('id')}"
            if item.get("authorUniqueId") and item.get("id") else None
        ),
    }


def normalise_playlist_info(info: dict, playlist_type: str | None) -> dict:
    """`embedInfo` from a hashtag or music embed: the entity behind the list."""
    return {
        "playlistType": playlist_type,
        "entityId": str(info.get("id")) if info.get("id") is not None else None,
        "musicArtist": info.get("artist"),
        "entityVideoCount": first_int(info.get("videoCount")),
        "entityCoverUrl": first_url(info.get("coverUrl")),
    }


def normalise_oembed(payload: dict) -> dict:
    """The public oEmbed object, flattened. `html` is dropped -- it is an iframe."""
    return {
        "videoId": str(payload.get("embed_product_id")) if payload.get("embed_product_id") else None,
        "title": payload.get("title"),
        "authorUniqueId": payload.get("author_unique_id"),
        "authorNickname": payload.get("author_name"),
        "authorProfileUrl": payload.get("author_url"),
        "thumbnailUrl": payload.get("thumbnail_url"),
        "thumbnailWidth": first_int(payload.get("thumbnail_width")),
        "thumbnailHeight": first_int(payload.get("thumbnail_height")),
        "embedWidth": first_int(payload.get("width")),
        "embedHeight": first_int(payload.get("height")),
        "embedType": payload.get("embed_type"),
        "providerName": payload.get("provider_name"),
    }
