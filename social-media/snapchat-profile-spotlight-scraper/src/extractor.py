"""Payload -> dataset records.

Shaping rules follow .ai/conventions/dataset-envelope.md: friendly fields are
*added on top of* Snapchat's own objects, never substituted. Every record keeps
the untouched upstream object under ``_raw`` because Snapchat adds and drops
keys without notice (``bitmoji3d``, ``thumbnailTiles`` and ``contextCards`` all
appear on some accounts only).

Three upstream quirks this module absorbs, all observed during recon:

* **Counts arrive as strings** (``subscriberCount: "758800"``,
  ``viewCount: "24931"``). They are parsed to integers in a parallel ``*Count``
  field so a dataset can be sorted numerically, while the original string stays
  in ``_raw``.
* **Zero is not "unknown".** ``netflix`` publishes ``subscriberCount: "0"`` and
  really does hide the number, while ``nasa`` publishes 758800. The parsed field
  is therefore ``0`` for Netflix and never coerced to ``null`` -- the caller can
  tell "hidden" from "absent" by checking ``_raw``.
* **Spotlight arrives as two parallel arrays.** ``spotlightStoryMetadata[i]``
  (video stats) and ``spotlightHighlights[i]`` (media URLs) describe the same
  post, matched by index. Both lists had identical lengths on every account
  probed (7 / 24 / 30), but the pairing is done defensively with ``.get`` so a
  mismatch degrades to "stats without media" instead of raising.
"""

from datetime import datetime, timezone

from src.constants import BADGE_NAMES, BASE, CATEGORY_PREFIXES, STORY_TYPE_NAMES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_int(value):
    """Snapchat sends counts as strings. Returns None when the field is absent
    or not numeric -- never 0, which is a real, different answer."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def ms_to_iso(value):
    ms = to_int(value)
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def sec_to_iso(value):
    s = to_int(value)
    if s is None:
        return None
    try:
        return datetime.fromtimestamp(s, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def unwrap(value):
    """Snapchat wraps *some* optional scalars in a {"value": ...} box and leaves
    others bare -- ``storyTitle`` arrives as {"value": "Moon Joy"} while
    ``storySubtitle`` on the same object is a plain string. Unwrapping in one
    place keeps that inconsistency out of every field mapping (caught by the
    local smoke test, which printed a dict where a title belonged)."""
    if isinstance(value, dict) and set(value.keys()) == {"value"}:
        return value["value"]
    return value


def _strip_category(key):
    if not key:
        return None
    for prefix in CATEGORY_PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix):].replace("-", " ")
    return key


def normalize_record(record: dict) -> dict:
    """Last line of defence against Snapchat's {"value": ...} boxes.

    Any *new* boxed scalar Snapchat introduces would otherwise reach the
    dataset as a dict where the schema declares a string, which the platform
    rejects at push time (this bit three Actors in this repo before). Every
    top-level field is unwrapped here; nested payloads (_raw, snaps, sample)
    are left exactly as upstream sent them.
    """
    skip = {"_raw", "snaps", "sample", "relatedAccounts", "contextCards", "lensResource"}
    for key, value in record.items():
        if key not in skip:
            record[key] = unwrap(value)
    return record


def _envelope(input_value: str, source: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def profile_info(page_props: dict) -> dict:
    """Lift the profile object out of pageProps.

    ``userProfile`` is a tagged union: ``$case`` names which member is set
    (``publicProfileInfo`` for creator/brand accounts). Reading ``$case``
    instead of hardcoding one key means a business-profile variant still
    resolves instead of returning {}.
    """
    up = page_props.get("userProfile") or {}
    case = up.get("$case")
    if case and isinstance(up.get(case), dict):
        return up[case]
    for key in ("publicProfileInfo", "businessProfileInfo", "userProfileInfo"):
        if isinstance(up.get(key), dict):
            return up[key]
    return {}


def _related_summary(related) -> list[dict]:
    """Related accounts ship as nested profile objects with most fields blank --
    only username/title/badge/picture are populated. Flattened to that useful
    subset; the full nested object stays in the parent record's _raw."""
    out = []
    for item in related or []:
        info = item.get("publicProfileInfo") if isinstance(item, dict) else None
        if not isinstance(info, dict):
            continue
        out.append(
            {
                "username": info.get("username"),
                "title": info.get("title"),
                "badge": info.get("badge"),
                "profilePictureUrl": info.get("profilePictureUrl"),
                "profileUrl": f"{BASE}/@{info.get('username')}" if info.get("username") else None,
            }
        )
    return out


def wrap_profile(username: str, page_props: dict) -> dict:
    info = profile_info(page_props)
    related = _related_summary(info.get("relatedAccountsInfo"))
    badge = info.get("badge")

    record = _envelope(username, "S1-next-data", "PROFILE")
    record.update(
        {
            "username": info.get("username") or username,
            "displayName": unwrap(info.get("title")) or None,
            "profileUrl": f"{BASE}/@{info.get('username') or username}",
            "bio": unwrap(info.get("bio")) or None,
            "websiteUrl": unwrap(info.get("websiteUrl")) or None,
            "address": unwrap(info.get("address")) or None,
            "subscriberCount": to_int(info.get("subscriberCount")),
            "badge": badge,
            "badgeName": BADGE_NAMES.get(badge, str(badge) if badge is not None else None),
            "isVerified": bool(badge),
            "category": _strip_category(info.get("categoryStringId")),
            "subcategory": _strip_category(info.get("subcategoryStringId")),
            "profilePictureUrl": info.get("profilePictureUrl") or None,
            "squareHeroImageUrl": info.get("squareHeroImageUrl") or None,
            "snapcodeImageUrl": info.get("snapcodeImageUrl") or None,
            "hasStory": info.get("hasStory"),
            "hasCuratedHighlights": info.get("hasCuratedHighlights"),
            "hasSpotlightHighlights": info.get("hasSpotlightHighlights"),
            "createdAt": ms_to_iso(info.get("creationTimestampMs")),
            "updatedAt": ms_to_iso(info.get("lastUpdateTimestampMs")),
            "lensCount": len(page_props.get("lenses") or []),
            "curatedHighlightCount": len(page_props.get("curatedHighlights") or []),
            "spotlightCount": len(page_props.get("spotlightStoryMetadata") or []),
            "relatedAccountCount": len(related),
            "relatedAccounts": related,
            "_buildId": page_props.get("_buildId"),
            "_raw": info,
        }
    )
    return normalize_record(record)


def _creator(video_meta: dict) -> dict:
    """creator is a tagged union too ($case = personCreator | ...)."""
    creator = video_meta.get("creator") or {}
    case = creator.get("$case")
    inner = creator.get(case) if case and isinstance(creator.get(case), dict) else {}
    return inner or {}


def wrap_spotlight(username: str, index: int, meta: dict, highlight: dict | None) -> dict:
    video = (meta or {}).get("videoMetadata") or {}
    creator = _creator(video)
    snaps = (highlight or {}).get("snapList") or []
    first_snap = snaps[0] if snaps else {}
    snap_urls = first_snap.get("snapUrls") or {}
    preview = snap_urls.get("mediaPreviewUrl") or {}

    record = _envelope(username, "S1-next-data", "SPOTLIGHT_VIDEO")
    record.update(
        {
            "username": username,
            "spotlightIndex": index,
            "storyId": unwrap((highlight or {}).get("storyId")),
            "highlightId": unwrap((highlight or {}).get("highlightId")),
            "title": unwrap(video.get("name")) or None,
            "description": unwrap(video.get("description")) or None,
            "caption": unwrap(video.get("embeddedTextCaption")) or None,
            "viewCount": to_int(video.get("viewCount")),
            "shareCount": to_int(video.get("shareCount")),
            "durationMs": to_int(video.get("durationMs")),
            "width": video.get("width"),
            "height": video.get("height"),
            "uploadedAt": ms_to_iso(video.get("uploadDateMs")),
            "videoUrl": video.get("contentUrl") or snap_urls.get("mediaUrl") or None,
            "thumbnailUrl": video.get("thumbnailUrl") or (preview.get("value") if isinstance(preview, dict) else None),
            "keywords": video.get("keywords") or [],
            "hashtags": (meta or {}).get("hashtags") or [],
            "creatorUsername": creator.get("username") or username,
            "creatorName": creator.get("name") or None,
            "creatorFollowerCount": to_int(creator.get("followerCount")),
            "creatorUrl": creator.get("url") or f"{BASE}/@{username}",
            "snapCount": len(snaps),
            "contextCards": (meta or {}).get("contextCards") or [],
            "_raw": {"metadata": meta, "highlight": highlight},
        }
    )
    return normalize_record(record)


def wrap_highlight(username: str, index: int, story: dict, kind: str) -> dict:
    snaps = story.get("snapList") or []
    parsed_snaps = []
    for snap in snaps:
        urls = snap.get("snapUrls") or {}
        preview = urls.get("mediaPreviewUrl") or {}
        ts = snap.get("timestampInSec") or {}
        parsed_snaps.append(
            {
                "snapIndex": snap.get("snapIndex"),
                "snapId": (snap.get("snapId") or {}).get("value") or None,
                "mediaType": snap.get("snapMediaType"),
                "mediaUrl": urls.get("mediaUrl") or None,
                "previewUrl": preview.get("value") if isinstance(preview, dict) else None,
                "timestamp": sec_to_iso(ts.get("value") if isinstance(ts, dict) else ts),
                "isSponsored": snap.get("isSponsored"),
            }
        )

    story_type = story.get("storyType")
    record = _envelope(username, "S1-next-data", "HIGHLIGHT")
    record.update(
        {
            "username": username,
            "highlightIndex": index,
            "highlightKind": kind,
            "storyType": story_type,
            "storyTypeName": STORY_TYPE_NAMES.get(story_type, str(story_type) if story_type is not None else None),
            "storyId": unwrap(story.get("storyId")),
            "highlightId": unwrap(story.get("highlightId")),
            "title": unwrap(story.get("storyTitle")) or None,
            "subtitle": unwrap(story.get("storySubtitle")) or None,
            "emoji": unwrap(story.get("emoji")) or None,
            "thumbnailUrl": unwrap(story.get("thumbnailUrl")) or None,
            "videoTrackUrl": unwrap(story.get("videoTrackUrl")) or None,
            "canonicalUrl": (
                f"{BASE}{story['canonicalUrlSuffix']}" if story.get("canonicalUrlSuffix") else None
            ),
            "snapCount": len(parsed_snaps),
            "firstSnapAt": next((s["timestamp"] for s in parsed_snaps if s["timestamp"]), None),
            "snaps": parsed_snaps,
            "_raw": story,
        }
    )
    return normalize_record(record)


def wrap_lens(input_value: str, lens: dict, category: str | None = None) -> dict:
    record = _envelope(input_value, "S1-next-data", "LENS")
    record.update(
        {
            "lensId": lens.get("lensId") or None,
            "lensName": lens.get("lensName") or None,
            "scannableUuid": lens.get("scannableUuid") or None,
            "creatorUsername": lens.get("lensCreatorUsername") or None,
            "creatorDisplayName": lens.get("lensCreatorDisplayName") or None,
            "creatorProfileUrl": lens.get("userProfileUrl") or None,
            "isOfficialSnapLens": lens.get("isOfficialSnapLens"),
            "category": category,
            "searchTags": lens.get("lensCreatorSearchTags") or [],
            "previewImageUrl": lens.get("lensPreviewImageUrl") or None,
            "previewVideoUrl": lens.get("lensPreviewVideoUrl") or None,
            "iconUrl": lens.get("iconUrl") or None,
            "scannableImageUrl": lens.get("scannableImageUrl") or None,
            "unlockUrl": lens.get("unlockUrl") or None,
            "lensResource": lens.get("lensResource"),
            "lastUpdatedEpoch": to_int(lens.get("lastUpdatedEpoch")),
            "_raw": lens,
        }
    )
    return normalize_record(record)


def wrap_trending(index: int, item: dict) -> dict:
    """One entry of the /spotlight hub feed.

    The hub wraps each post as {story, metadata, contentSource}; the inner
    ``story`` has the same shape as a profile's spotlightHighlights entry, so
    the same snap parsing applies.
    """
    story = item.get("story") or {}
    meta = item.get("metadata") or {}
    video = meta.get("videoMetadata") or meta
    creator = _creator(video) if isinstance(video, dict) else {}
    snaps = story.get("snapList") or []
    first = snaps[0] if snaps else {}
    urls = first.get("snapUrls") or {}
    preview = urls.get("mediaPreviewUrl") or {}

    record = _envelope("trending", "S1-next-data", "TRENDING_SPOTLIGHT")
    record.update(
        {
            "feedIndex": index,
            "storyId": unwrap(story.get("storyId")),
            "title": unwrap(story.get("storyTitle")) or (unwrap(video.get("name")) if isinstance(video, dict) else None),
            "subtitle": unwrap(story.get("storySubtitle")) or None,
            "viewCount": to_int(video.get("viewCount")) if isinstance(video, dict) else None,
            "shareCount": to_int(video.get("shareCount")) if isinstance(video, dict) else None,
            "durationMs": to_int(video.get("durationMs")) if isinstance(video, dict) else None,
            "uploadedAt": ms_to_iso(video.get("uploadDateMs")) if isinstance(video, dict) else None,
            "creatorUsername": creator.get("username") or None,
            "creatorName": creator.get("name") or None,
            "creatorUrl": creator.get("url") or None,
            "creatorFollowerCount": to_int(creator.get("followerCount")),
            "videoUrl": (video.get("contentUrl") if isinstance(video, dict) else None) or urls.get("mediaUrl") or None,
            "thumbnailUrl": story.get("thumbnailUrl")
            or (video.get("thumbnailUrl") if isinstance(video, dict) else None)
            or (preview.get("value") if isinstance(preview, dict) else None),
            "canonicalUrl": (
                f"{BASE}{story['canonicalUrlSuffix']}" if story.get("canonicalUrlSuffix") else None
            ),
            "contentSource": item.get("contentSource"),
            "snapCount": len(snaps),
            "_raw": item,
        }
    )
    return normalize_record(record)


def wrap_reference(surface: str, url: str, ok: bool, detail: str, sample: dict | None = None) -> dict:
    record = _envelope("reference", "S1-next-data" if ok else "none", "SURFACE")
    record.update(
        {
            "surface": surface,
            "url": url,
            "isAvailable": ok,
            "detail": detail,
            "sample": sample or {},
        }
    )
    return normalize_record(record)


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, "none", "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
