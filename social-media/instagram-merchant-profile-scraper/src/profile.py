"""Profile parsing across three strategies, plus bio-link classification."""

import html as htmllib
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

from src.constants import (
    LINK_PLATFORMS,
    ORIGIN,
    SOURCE_API,
    SOURCE_HTML,
    SOURCE_META,
)

logger = logging.getLogger(__name__)

_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_JSON_BLOCK = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
_META = re.compile(
    r'<meta (?:property|name)="og:(title|description|image)" content="([^"]*)"'
)
# "680K Followers, 150 Following, 7,483 Posts - See Instagram photos..."
_COUNTS = re.compile(
    r"([\d.,]+[KMB]?)\s+Followers,\s*([\d.,]+[KMB]?)\s+Following,\s*([\d.,]+[KMB]?)\s+Posts",
    re.I,
)


class InvalidInput(ValueError):
    """The input is not a usable Instagram username or profile URL."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_username(raw: str) -> str:
    """Accept @handle, bare handle, or any instagram.com profile URL."""
    value = str(raw or "").strip()
    if not value:
        raise InvalidInput("empty entry")
    value = value.lstrip("@")
    if "/" in value or "instagram.com" in value.lower():
        parsed = urlparse(value if "//" in value else "https://" + value)
        if "instagram.com" not in (parsed.netloc or "").lower():
            raise InvalidInput(f"{raw!r} is not an instagram.com URL")
        segments = [s for s in (parsed.path or "").split("/") if s]
        if not segments:
            raise InvalidInput(f"{raw!r} has no username in its path")
        value = segments[0]
    if not _USERNAME.match(value):
        raise InvalidInput(
            f"{raw!r} is not a valid Instagram username. Expected a handle like "
            "'cottonink' or a profile URL."
        )
    return value.lower()


def parse_count(text) -> int | None:
    """'680K' / '7,483' / '1.2M' -> int."""
    if not isinstance(text, str) or not text.strip():
        return None
    value = text.strip().replace(",", "")
    multiplier = 1
    if value[-1:].upper() in ("K", "M", "B"):
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[value[-1].upper()]
        value = value[:-1]
    try:
        return int(float(value) * multiplier)
    except ValueError:
        return None


def unwrap_link(url: str | None) -> str | None:
    """Strip Instagram's `l.instagram.com/?u=<encoded>` redirect wrapper."""
    if not isinstance(url, str) or not url:
        return None
    if "l.instagram.com" not in url and "l.facebook.com" not in url:
        return url
    target = parse_qs(urlparse(url).query).get("u")
    return unquote(target[0]) if target else url


def classify_link(url: str | None) -> str | None:
    """Label a bio link with the platform a merchant is actually selling on."""
    if not isinstance(url, str) or not url:
        return None
    lowered = url.lower()
    for needle, label in LINK_PLATFORMS.items():
        if needle in lowered:
            return label
    return "OTHER"


def normalise_bio_links(raw_links, external_url) -> list[dict]:
    """One clean list of destination links, deduped, with platform labels."""
    out: list[dict] = []
    seen: set[str] = set()

    for link in raw_links or []:
        if not isinstance(link, dict):
            continue
        # `url` is the clean destination; `lynx_url` is the wrapped form and
        # is only used when `url` is absent.
        target = link.get("url") or unwrap_link(link.get("lynx_url"))
        if not target or target in seen:
            continue
        seen.add(target)
        out.append({
            "url": target,
            "title": link.get("title") or None,
            "linkType": link.get("link_type"),
            "platform": classify_link(target),
        })

    external = unwrap_link(external_url)
    if external and external not in seen:
        out.append({
            "url": external, "title": None,
            "linkType": "external_url", "platform": classify_link(external),
        })
    return out


def _business_address(raw):
    """`business_address_json` ships as a JSON *string*."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _post_record(node: dict) -> dict:
    caption_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
    caption = (caption_edges[0].get("node", {}) or {}).get("text") if caption_edges else None
    taken = node.get("taken_at_timestamp")
    return {
        "shortcode": node.get("shortcode"),
        "url": f"{ORIGIN}/p/{node['shortcode']}/" if node.get("shortcode") else None,
        "caption": caption,
        "likes": (node.get("edge_media_preview_like") or {}).get("count"),
        "comments": (node.get("edge_media_to_comment") or {}).get("count"),
        "isVideo": node.get("is_video"),
        "mediaUrl": node.get("display_url"),
        "videoUrl": node.get("video_url"),
        "videoViews": node.get("video_view_count"),
        # `product_type` here is Instagram's MEDIA type (feed/clips/igtv),
        # not a shopping product -- see CRAWLING_METHOD.md.
        "mediaType": node.get("product_type"),
        "takenAt": (
            datetime.fromtimestamp(taken, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(taken, (int, float)) and taken > 0 else None
        ),
    }


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def from_api(username: str, user: dict, max_posts: int) -> dict:
    """S1 -- richest. Only source of business contact/address and posts."""
    address = _business_address(user.get("business_address_json"))
    media = (user.get("edge_owner_to_timeline_media") or {})
    posts = [
        _post_record(e["node"]) for e in (media.get("edges") or [])
        if isinstance(e, dict) and isinstance(e.get("node"), dict)
    ]
    if max_posts:
        posts = posts[:max_posts]

    return {
        "_input": username,
        "_source": SOURCE_API,
        "_scrapedAt": _now(),
        "username": user.get("username") or username,
        "userId": user.get("id"),
        "fullName": user.get("full_name"),
        "biography": user.get("biography"),
        "isVerified": user.get("is_verified"),
        "isPrivate": user.get("is_private"),
        "isBusinessAccount": user.get("is_business_account"),
        "isProfessionalAccount": user.get("is_professional_account"),
        "categoryName": user.get("category_name") or user.get("business_category_name"),
        "followers": (user.get("edge_followed_by") or {}).get("count"),
        "following": (user.get("edge_follow") or {}).get("count"),
        "postCount": media.get("count"),
        "profilePicUrl": user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
        "profileUrl": f"{ORIGIN}/{username}/",
        # business contact -- API-only
        "businessEmail": user.get("business_email"),
        "businessPhone": user.get("business_phone_number"),
        "businessContactMethod": user.get("business_contact_method"),
        "businessCity": (address or {}).get("city_name"),
        "businessStreet": (address or {}).get("street_address"),
        "businessZip": (address or {}).get("zip_code"),
        "businessLatitude": (address or {}).get("latitude"),
        "businessLongitude": (address or {}).get("longitude"),
        "bioLinks": normalise_bio_links(user.get("bio_links"), user.get("external_url")),
        "recentPosts": posts,
    }


def _find_user_object(data):
    """Depth-first hunt for the embedded user dict in an HTML JSON block."""
    if isinstance(data, dict):
        if "biography" in data and "username" in data:
            yield data
        for value in data.values():
            yield from _find_user_object(value)
    elif isinstance(data, list):
        for value in data:
            yield from _find_user_object(value)


def from_html(username: str, page_html: str) -> dict | None:
    """S2 -- the profile page's own embedded JSON.

    Reliable where the API intermittently returns nothing, but carries no
    business address/contact fields and no posts.
    """
    best = None
    for block in _JSON_BLOCK.findall(page_html or ""):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for user in _find_user_object(data):
            if best is None or len(user) > len(best):
                best = user
    if not best:
        return None

    return {
        "_input": username,
        "_source": SOURCE_HTML,
        "_scrapedAt": _now(),
        "username": best.get("username") or username,
        "userId": best.get("id") or best.get("pk"),
        "fullName": best.get("full_name"),
        "biography": best.get("biography"),
        "isVerified": best.get("is_verified"),
        "isPrivate": best.get("is_private"),
        "followers": best.get("follower_count"),
        "following": best.get("following_count"),
        "postCount": best.get("all_media_count"),
        "profilePicUrl": best.get("profile_pic_url"),
        "profileUrl": f"{ORIGIN}/{username}/",
        "bioLinks": normalise_bio_links(best.get("bio_links"), None),
        "recentPosts": [],
    }


def from_meta(username: str, page_html: str) -> dict | None:
    """S3 -- degraded. og: tags only; counts are rounded ('680K')."""
    tags = {name: value for name, value in _META.findall(page_html or "")}
    if not tags:
        return None
    description = htmllib.unescape(tags.get("description", ""))
    title = htmllib.unescape(tags.get("title", ""))
    match = _COUNTS.search(description)
    full_name = title.split("(")[0].strip() or None

    return {
        "_input": username,
        "_source": SOURCE_META,
        "_scrapedAt": _now(),
        "username": username,
        "fullName": full_name,
        "followers": parse_count(match.group(1)) if match else None,
        "following": parse_count(match.group(2)) if match else None,
        "postCount": parse_count(match.group(3)) if match else None,
        "profilePicUrl": htmllib.unescape(tags.get("image", "")) or None,
        "profileUrl": f"{ORIGIN}/{username}/",
        "bioLinks": [],
        "recentPosts": [],
        # og counts are rounded by Instagram; flag it rather than implying
        # they are exact.
        "_warning": "counts_are_rounded_og_values",
    }


def enrich(record: dict) -> dict:
    """Derived fields a merchant-mapping consumer would otherwise compute."""
    links = record.get("bioLinks") or []
    platforms = sorted({link["platform"] for link in links if link.get("platform")})
    marketplaces = sorted({
        p for p in platforms
        if p in ("SHOPEE", "TOKOPEDIA", "BLIBLI", "LAZADA", "BUKALAPAK", "TIKTOK", "SHOPIFY")
    })
    followers, posts = record.get("followers"), record.get("postCount")
    recent = record.get("recentPosts") or []
    engagements = [
        (p.get("likes") or 0) + (p.get("comments") or 0)
        for p in recent if p.get("likes") is not None
    ]
    record["bioLinkCount"] = len(links)
    record["linkPlatforms"] = platforms
    record["marketplaces"] = marketplaces
    record["sellsOnMarketplace"] = bool(marketplaces)
    record["hasWhatsApp"] = "WHATSAPP" in platforms
    record["primaryShopLink"] = links[0]["url"] if links else None
    record["postsPerFollower"] = (
        round(posts / followers, 6) if isinstance(posts, int) and followers else None
    )
    # Engagement rate over the posts actually returned -- only meaningful
    # when posts were fetched at all.
    record["avgEngagementPerPost"] = (
        round(sum(engagements) / len(engagements), 1) if engagements else None
    )
    record["engagementRatePercent"] = (
        round(sum(engagements) / len(engagements) / followers * 100, 4)
        if engagements and followers else None
    )
    return record
