"""Pull reviews, rating aggregates and sentiment tags for one Traveloka object."""

from __future__ import annotations

import datetime as dt
import logging
import re
from urllib.parse import urlsplit

from src.client import TravelokaError
from src.constants import (
    FALLBACK_CONFIG_IDS,
    FEATURE_CONFIG,
    FEATURE_KEY,
    GET_AGGREGATE,
    GET_COUNT,
    GET_RATING_TAGS,
    GET_REVIEWS,
    PRODUCT_PRESETS,
    REFERER_ACTIVITY,
    REFERER_HOTEL,
)

logger = logging.getLogger(__name__)

_TRAILING_ID = re.compile(r"-(\d{3,})(?:[/?#]|$)")
_BARE_ID = re.compile(r"^\d{3,}$")


def _num(value):
    if value in (None, "", "null"):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return int(out) if out.is_integer() else out


def detect_product(url: str) -> str | None:
    """Guess the product family from a Traveloka URL path."""
    path = (urlsplit(url).path or "").lower()
    if "/activities/" in path or "/xperience" in path:
        return "experience"
    if "/hotel" in path:
        return "hotel"
    if "/bus-and-shuttle" in path or "/bus" in path:
        return "bus"
    if "/airport-transfer" in path:
        return "airport-transfer"
    if "/car-rental" in path or "/rental" in path:
        return "car-rental"
    return None


def object_id_from_url(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if _BARE_ID.match(value):
        return value
    match = _TRAILING_ID.search(urlsplit(value).path or value)
    return match.group(1) if match else None


async def load_config_ids(client) -> dict:
    """Read Traveloka's own productType -> configId map, falling back if absent."""
    path, domain = FEATURE_CONFIG
    try:
        payload = await client.call_async(path, domain, {}, REFERER_HOTEL)
    except TravelokaError as exc:
        logger.warning("Feature config unavailable (%s); using the built-in map.", exc)
        return dict(FALLBACK_CONFIG_IDS)

    feature = (payload.get("features") or {}).get(FEATURE_KEY) or {}
    properties = feature.get("properties") or {}
    if not properties:
        logger.warning("Feature key %s is empty; using the built-in map.", FEATURE_KEY)
        return dict(FALLBACK_CONFIG_IDS)

    merged = dict(FALLBACK_CONFIG_IDS)
    merged.update(properties)
    logger.info("Loaded %d review config IDs from Traveloka feature control.",
                len(properties))
    return merged


def resolve_config(product: str, config_ids: dict) -> tuple[str, str, str]:
    """Return (configId, productType, referer) for a product preset."""
    key, product_type, referer = PRODUCT_PRESETS[product]
    config_id = config_ids.get(key) or FALLBACK_CONFIG_IDS.get(key)
    if not config_id:
        raise TravelokaError(f"No review config ID is known for {product!r}.")
    return config_id, product_type, referer


async def fetch_aggregate(client, object_id: str, config_id: str,
                          product_type: str, referer: str) -> dict:
    path, domain = GET_AGGREGATE
    payload = await client.call_async(
        path, domain,
        {"configId": config_id, "objectId": object_id, "productType": product_type,
         "withDistributions": True, "withAISummary": True, "origin": "FALLBACK"},
        referer)
    aggregate = payload.get("reviewAggregate") or {}
    return {
        "objectName": aggregate.get("objectName"),
        "rating": _num(aggregate.get("overallRating")),
        "ratingScale": _num(aggregate.get("maximumRating")),
        "ratingLabel": aggregate.get("textRating"),
        "totalReviewCount": _num(aggregate.get("count")),
        "distributions": aggregate.get("ratingDistributions")
        or aggregate.get("distributions"),
    }


async def fetch_rating_tags(client, object_id: str, config_id: str,
                            product_type: str, referer: str) -> list[dict]:
    """Aspect tags with counts -- the closest thing to built-in sentiment."""
    path, domain = GET_RATING_TAGS
    payload = await client.call_async(
        path, domain,
        {"configId": config_id, "objectId": object_id, "productType": product_type,
         "filter": {}, "origin": "TRAVELOKA"},
        referer)
    tags = []
    for tag in payload.get("ratingTags") or []:
        ids = tag.get("ratingTagIds") or []
        tags.append({
            "label": tag.get("ratingTagLabel"),
            "count": _num(tag.get("count")),
            "tagIds": ids,
            # Traveloka bundles GOOD_/BAD_ variants under one label; the split
            # tells you whether an aspect is praised or complained about.
            "positiveTagIds": [t for t in ids if t.startswith("GOOD_")],
            "negativeTagIds": [t for t in ids if t.startswith("BAD_")],
        })
    return tags


async def fetch_count(client, object_id: str, config_id: str,
                      product_type: str, referer: str,
                      review_filter: dict) -> int | None:
    path, domain = GET_COUNT
    payload = await client.call_async(
        path, domain,
        {"configId": config_id, "objectId": object_id, "productType": product_type,
         "filter": review_filter, "origin": "TRAVELOKA"},
        referer)
    return _num(payload.get("count"))


def shape_review(raw: dict, object_id: str, object_name: str | None) -> dict:
    reviewer = raw.get("reviewer") or {}
    media = raw.get("reviewMedia") or []
    reply = raw.get("reviewReply") or {}
    reaction = raw.get("reactionSummary") or {}

    timestamp = _num(raw.get("reviewTimestamp"))
    reviewed_at = None
    if timestamp:
        # The field is milliseconds since epoch, delivered as a string.
        reviewed_at = dt.datetime.fromtimestamp(
            timestamp / 1000, dt.timezone.utc).isoformat(timespec="seconds")

    sub_ratings = {}
    for entry in raw.get("subRatingInformations") or []:
        if isinstance(entry, dict) and entry.get("label"):
            sub_ratings[entry["label"]] = _num(entry.get("score"))

    return {
        "recordType": "REVIEW",
        "reviewId": raw.get("reviewId"),
        "objectId": object_id,
        "objectName": object_name,
        "productType": raw.get("productType"),
        "reviewedAt": reviewed_at,
        "reviewTimestampMs": timestamp,
        "score": _num(raw.get("reviewScore")),
        "scoreScale": _num(raw.get("reviewMaxScore")),
        "text": raw.get("reviewContentText"),
        "originalText": raw.get("reviewOriginalText"),
        "isMachineTranslated": raw.get("translationStatus") == "GOOGLE_TRANSLATE",
        "reviewerName": reviewer.get("reviewerName"),
        "reviewerStatus": reviewer.get("reviewerStatus"),
        "reviewerPhotoUrl": reviewer.get("reviewerPhotoUrl"),
        "subRatings": sub_ratings or None,
        "photoUrls": [m.get("reviewMediaUrl") for m in media
                      if isinstance(m, dict) and m.get("reviewMediaType") == "PHOTO"
                      and m.get("reviewMediaUrl")],
        "videoUrls": [m.get("reviewMediaUrl") for m in media
                      if isinstance(m, dict) and m.get("reviewMediaType") == "VIDEO"
                      and m.get("reviewMediaUrl")],
        "mediaCount": len(media),
        "helpfulCount": _num(reaction.get("reactionCount")),
        "propertyReplyText": reply.get("replyText") or reply.get("content"),
        "reviewSource": raw.get("reviewProvider") or raw.get("reviewOrigin"),
    }


async def fetch_reviews(client, object_id: str, config_id: str, product_type: str,
                        referer: str, max_reviews: int, page_size: int,
                        sort: str, review_filter: dict, rating_tags: list[str],
                        object_name: str | None):
    """Page through reviews, newest first by default.

    `sort` is sent as a bare string on purpose: the API accepts an object form
    with HTTP 200 and then ignores it, which silently returns unsorted data.
    """
    path, domain = GET_REVIEWS
    collected: list[dict] = []
    skip = 0
    seen: set[str] = set()

    while len(collected) < max_reviews:
        want = min(page_size, max_reviews - len(collected))
        payload = await client.call_async(
            path, domain,
            {
                "objectId": object_id,
                "productType": product_type,
                "configId": config_id,
                "filter": review_filter,
                "sort": sort,
                "origin": "TRAVELOKA",
                "ratingTagSet": rating_tags,
                "limit": str(want),
                "skip": str(skip),
            },
            referer)

        if payload.get("status") != "SUCCESS":
            raise TravelokaError(
                f"Review service answered status {payload.get('status')!r} for "
                f"object {object_id}. Check that the product type matches the URL."
            )

        batch = payload.get("reviews") or []
        if not batch:
            break

        fresh = 0
        for raw in batch:
            shaped = shape_review(raw, object_id, object_name)
            key = shaped.get("reviewId") or f"{skip}:{fresh}"
            if key in seen:
                continue
            seen.add(key)
            collected.append(shaped)
            fresh += 1

        skip += len(batch)
        if not payload.get("hasNext") or fresh == 0:
            break

    return collected
