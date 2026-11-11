"""Input parsing and normalisation of Instagram's Relay node shapes.

Instagram returns the same media entity in four different widths depending on
which surface served it, and the differences are not cosmetic -- they decide
what a consumer can actually compute:

* **profile timeline node** -- grid thumbnails. No engagement counts at all.
* **profile reels node** -- carries `like_count`, `comment_count`, `play_count`.
* **post-detail node** -- adds `taken_at`, `location`, `usertags`, image
  candidates. Wrapped in `if_not_gated_logged_out`.
* **location tab node** -- the widest (69 fields), including `video_versions`
  and `carousel_media`.

`normalise_media` maps all four onto one flat row so a dataset stays joinable,
and leaves a field `None` when the serving surface genuinely did not carry it.
A missing count is reported as null rather than 0 -- writing 0 for "the grid
view does not publish likes" would silently corrupt any average a consumer
computes.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.constants import ORIGIN

# media_type is an Instagram enum shared across most of the Graph surface.
MEDIA_TYPES = {1: "IMAGE", 2: "VIDEO", 8: "CAROUSEL"}

# ...but the reels tab omits `media_type` entirely and only ships `__typename`,
# so the kind is recovered from the type name there.
TYPENAME_KINDS = (
    ("carousel", "CAROUSEL"),
    ("sidecar", "CAROUSEL"),
    ("video", "VIDEO"),
    ("clips", "VIDEO"),
    ("image", "IMAGE"),
    ("photo", "IMAGE"),
)


def _media_kind(node: dict) -> str | None:
    """IMAGE / VIDEO / CAROUSEL from whichever field the surface provides."""
    kind = MEDIA_TYPES.get(node.get("media_type"))
    if kind:
        return kind
    typename = node.get("__typename")
    if isinstance(typename, str):
        lowered = typename.lower()
        for needle, mapped in TYPENAME_KINDS:
            if needle in lowered:
                return mapped
    # The reels tab is all video even when Instagram renames the type.
    if node.get("product_type") == "clips" or node.get("play_count") is not None:
        return "VIDEO"
    return None

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]{5,20}$")
_POST_URL_RE = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
_PROFILE_URL_RE = re.compile(r"instagram\.com/([A-Za-z0-9._]+)")
_LOCATION_URL_RE = re.compile(r"instagram\.com/explore/locations/(\d+)")

# Routes that look like a profile but are Instagram's own pages.
RESERVED_PATHS = {
    "p", "reel", "reels", "tv", "explore", "stories", "accounts", "direct",
    "about", "legal", "developer", "api", "graphql", "web", "emails", "session",
}


class InvalidInput(Exception):
    """An input entry cannot be turned into a scrape target."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------
def parse_username(raw: str) -> str:
    """A handle from a bare username, an @handle or a profile URL."""
    value = (raw or "").strip()
    if not value:
        raise InvalidInput("empty entry")
    value = value.lstrip("@")
    if "instagram.com" in value:
        if _POST_URL_RE.search(value):
            raise InvalidInput(f"{raw!r} is a post URL; use mode 'post_detail' for it")
        match = _PROFILE_URL_RE.search(value)
        if not match:
            raise InvalidInput(f"{raw!r} is not a recognisable Instagram profile URL")
        value = match.group(1)
    value = value.split("?")[0].split("#")[0].strip("/")
    if value.lower() in RESERVED_PATHS:
        raise InvalidInput(f"{raw!r} points at an Instagram system route, not a profile")
    if not _USERNAME_RE.match(value):
        raise InvalidInput(f"{raw!r} is not a valid Instagram username")
    return value


def parse_shortcode(raw: str) -> str:
    """A post shortcode from a /p/, /reel/, /reels/ or /tv/ URL, or a bare code."""
    value = (raw or "").strip()
    if not value:
        raise InvalidInput("empty entry")
    match = _POST_URL_RE.search(value)
    if match:
        return match.group(1)
    value = value.strip("/").split("/")[-1].split("?")[0]
    if not _SHORTCODE_RE.match(value):
        raise InvalidInput(f"{raw!r} is not a post URL or shortcode")
    return value


def parse_location_id(raw: str) -> str:
    """A numeric location id from a bare id or an /explore/locations/ URL."""
    value = (raw or "").strip()
    if not value:
        raise InvalidInput("empty entry")
    match = _LOCATION_URL_RE.search(value)
    if match:
        return match.group(1)
    value = value.strip("/").split("/")[0]
    if not value.isdigit():
        raise InvalidInput(f"{raw!r} is not a numeric Instagram location id or location URL")
    return value


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _text(node: Any) -> str | None:
    """Caption text, whether the caption is a dict or already a string."""
    if isinstance(node, dict):
        value = node.get("text")
        return value if isinstance(value, str) else None
    return node if isinstance(node, str) else None


def _epoch_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def _best_video_url(node: dict) -> str | None:
    versions = node.get("video_versions")
    if not isinstance(versions, list):
        return None
    best, best_width = None, -1
    for version in versions:
        if not isinstance(version, dict):
            continue
        width = version.get("width") or 0
        url = version.get("url")
        if isinstance(url, str) and isinstance(width, int) and width > best_width:
            best, best_width = url, width
    return best


def _image_url(node: dict) -> str | None:
    """Highest-resolution still available on whichever surface served this node."""
    candidates = ((node.get("image_versions2") or {}).get("candidates")
                  if isinstance(node.get("image_versions2"), dict) else None)
    if isinstance(candidates, list):
        best, best_width = None, -1
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            width = candidate.get("width") or 0
            url = candidate.get("url")
            if isinstance(url, str) and isinstance(width, int) and width > best_width:
                best, best_width = url, width
        if best:
            return best
    display = node.get("display_uri")
    return display if isinstance(display, str) else None


def _user_brief(node: Any) -> dict:
    if not isinstance(node, dict):
        return {"ownerUsername": None, "ownerId": None, "ownerFullName": None,
                "ownerIsVerified": None}
    return {
        "ownerUsername": node.get("username"),
        "ownerId": node.get("pk") or node.get("id"),
        "ownerFullName": node.get("full_name"),
        "ownerIsVerified": node.get("is_verified"),
    }


def _usertags(node: dict) -> list[str]:
    tags = node.get("usertags")
    inner = tags.get("in") if isinstance(tags, dict) else None
    out = []
    for entry in inner or []:
        user = entry.get("user") if isinstance(entry, dict) else None
        name = user.get("username") if isinstance(user, dict) else None
        if isinstance(name, str):
            out.append(name)
    return out


def _hashtags(caption: str | None) -> list[str]:
    if not caption:
        return []
    return list(dict.fromkeys(re.findall(r"#([A-Za-z0-9_À-ɏ]+)", caption)))


def _mentions(caption: str | None) -> list[str]:
    if not caption:
        return []
    return list(dict.fromkeys(re.findall(r"@([A-Za-z0-9._]+)", caption)))


def _location_brief(node: Any) -> dict:
    if not isinstance(node, dict):
        return {"locationId": None, "locationName": None}
    return {
        "locationId": node.get("pk") or node.get("id"),
        "locationName": node.get("name"),
    }


def normalise_media(node: dict) -> dict:
    """One media node from any surface, flattened to a stable row."""
    caption = _text(node.get("caption"))
    code = node.get("code")
    carousel = node.get("carousel_media")
    row = {
        "id": node.get("pk") or node.get("id"),
        "shortcode": code,
        "url": f"{ORIGIN}/p/{code}/" if code else None,
        "typename": node.get("__typename"),
        "mediaType": _media_kind(node),
        "productType": node.get("product_type"),
        "takenAt": _epoch_to_iso(node.get("taken_at")),
        "caption": caption,
        "hashtags": _hashtags(caption),
        "mentions": _mentions(caption),
        "accessibilityCaption": node.get("accessibility_caption"),
        # Counts are null, never 0, when the serving surface omits them -- the
        # profile grid genuinely does not publish engagement.
        "likeCount": node.get("like_count"),
        "commentCount": node.get("comment_count"),
        "playCount": node.get("play_count"),
        "viewCount": node.get("view_count"),
        "countsDisabled": node.get("like_and_view_counts_disabled"),
        "commentsDisabled": node.get("comments_disabled"),
        "isPaidPartnership": node.get("is_paid_partnership"),
        "imageUrl": _image_url(node),
        "videoUrl": _best_video_url(node),
        "hasAudio": node.get("has_audio"),
        "width": node.get("original_width"),
        "height": node.get("original_height"),
        "carouselCount": (
            node.get("carousel_media_count")
            or (len(carousel) if isinstance(carousel, list) else None)
        ),
        "taggedUsers": _usertags(node),
        "coauthors": [
            entry.get("username")
            for entry in (node.get("coauthor_producers") or [])
            if isinstance(entry, dict) and entry.get("username")
        ],
        **_user_brief(node.get("user")),
        **_location_brief(node.get("location")),
    }
    return row


def normalise_profile(node: dict) -> dict:
    """The `xig_user_by_username` profile payload, flattened."""
    links = []
    for link in node.get("bio_links") or []:
        if not isinstance(link, dict):
            continue
        links.append({
            "url": link.get("url"),
            "title": link.get("title"),
            "linkType": link.get("link_type"),
        })
    fb = node.get("linked_fb_info")
    return {
        "username": node.get("username"),
        "id": node.get("pk") or node.get("id"),
        "url": f"{ORIGIN}/{node.get('username')}/" if node.get("username") else None,
        "fullName": node.get("full_name"),
        "biography": node.get("biography"),
        "isVerified": node.get("is_verified"),
        "isPrivate": node.get("is_private"),
        "isUnpublished": node.get("is_unpublished"),
        "isMemorialized": node.get("is_memorialized"),
        "followerCount": node.get("follower_count"),
        "followingCount": node.get("following_count"),
        "mediaCount": node.get("all_media_count"),
        "hasClips": node.get("has_any_clips"),
        "pronouns": node.get("pronouns"),
        "profilePicUrl": node.get("profile_pic_url"),
        "accountBadges": node.get("account_badges"),
        "bioLinks": links,
        "hasThreadsBadge": node.get("show_text_post_app_badge"),
        "threadsBadgeLabel": node.get("text_post_app_badge_label"),
        "linkedFacebookPage": (fb or {}).get("linked_fb_page_name") if isinstance(fb, dict) else None,
    }


def normalise_comment(node: dict) -> dict:
    user = node.get("user") if isinstance(node.get("user"), dict) else {}
    return {
        "id": node.get("pk") or node.get("id"),
        "text": node.get("text"),
        "createdAt": _epoch_to_iso(node.get("created_at")),
        "likeCount": node.get("comment_like_count"),
        "replyCount": node.get("child_comment_count"),
        "parentCommentId": node.get("parent_comment_id"),
        "authorUsername": user.get("username"),
        "authorId": user.get("pk") or user.get("id"),
        "authorIsVerified": user.get("is_verified"),
        "authorProfilePicUrl": user.get("profile_pic_url"),
    }


def normalise_highlight(node: dict) -> dict:
    return {
        "id": node.get("id"),
        "title": node.get("title"),
        "coverUrl": node.get("cover_media_cropped_thumbnail_url"),
        "ownerUsername": node.get("owner_username"),
    }


def normalise_location(node: dict) -> dict:
    """`native_location_data.location_info` from the location page.

    Instagram returns empty strings, not nulls, for the address fields a place
    does not publish (a city has no street address). They are collapsed to None
    so a consumer can test one thing rather than two.
    """
    info = node.get("location_info") if isinstance(node.get("location_info"), dict) else node
    if not isinstance(info, dict):
        info = {}
    hours = info.get("hours") if isinstance(info.get("hours"), dict) else {}
    return {
        "locationId": info.get("location_id") or info.get("pk") or info.get("id"),
        "locationName": info.get("name"),
        "locationSlug": info.get("slug"),
        "locationCategory": info.get("category") or None,
        "locationMediaCount": info.get("media_count"),
        "latitude": info.get("lat"),
        "longitude": info.get("lng"),
        "phone": info.get("phone") or None,
        "priceRange": info.get("price_range"),
        "street": info.get("location_address") or None,
        "city": info.get("location_city") or None,
        "zipCode": info.get("location_zip") or None,
        "openingHoursStatus": hours.get("status") or None,
    }
