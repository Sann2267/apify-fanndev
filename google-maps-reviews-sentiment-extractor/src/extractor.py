"""Parse GetLocalBoqProxy responses into review records.

The response is a deeply nested positional array. Every index used here was
mapped empirically against live data (see CRAWLING_METHOD.md); the field map
itself lives in constants.py so a Google-side reshuffle is a one-file fix.

Positional arrays are hostile to defensive coding: a missing trailing element
is normal, but a *shifted* element silently yields wrong data. So the review
container is validated strictly (wrong shape raises UnexpectedShape) while
individual optional fields are read tolerantly through `_at`.
"""

from __future__ import annotations

import html as html_module
import re
from datetime import datetime, timezone
from typing import Any

from src.client import UnexpectedShape
from src.constants import (
    R_ATTRIBUTES,
    R_LANGUAGE,
    R_OWNER_RESPONSE,
    R_PERMALINK,
    R_PHOTOS,
    R_PLATFORM,
    R_RATING,
    R_RATING_MAX,
    R_REACTIONS,
    R_REPORT_URL,
    R_REVIEW_ID,
    R_REVIEWER,
    R_SOURCE_LANG_NAME,
    R_TARGET_LANG_NAME,
    R_TEXT,
    R_TEXT_DISPLAY,
    R_TIME,
    R_TRANSLATED_DISPLAY,
    R_TRANSLATED_TEXT,
    R_VISIT_MONTH,
    R_VISIT_TEXT,
    REACTION_LIKE_CATEGORY,
    RESP_REVIEW_NODE,
    RESP_REVIEWS_IDX,
    RESP_TOKEN_IDX,
)


_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]{1,40}>")


def clean_text(value: Any) -> Any:
    """Normalise Google's review/reply markup into plain text.

    Google embeds literal <br> tags and HTML entities in these fields. Field
    names and structure are still passed through verbatim (the portfolio's
    raw-passthrough rule); this only undoes presentation markup that would
    otherwise leak into CSV cells and skew sentiment scoring.
    """
    if not isinstance(value, str) or not value:
        return value
    text = _BR_RE.sub("\n", value)
    text = _TAG_RE.sub("", text)
    text = html_module.unescape(text)
    # Collapse the runs of blank lines that <br><br> leaves behind.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _at(seq: Any, index: int, default: Any = None) -> Any:
    """Read a positional slot, tolerating short arrays and nulls."""
    if not isinstance(seq, (list, tuple)) or index >= len(seq):
        return default
    value = seq[index]
    return default if value is None else value


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unwrap_response(payload: Any) -> tuple[list, str | None]:
    """Pull the review list and next-page cursor out of a decoded response.

    Returns ([], None) for the legitimate "no reviews" answer, but raises
    UnexpectedShape if the envelope itself no longer looks like we expect --
    an empty dataset caused by a schema change must not look like an empty
    dataset caused by a place having no reviews.
    """
    if payload is None:
        return [], None
    if not isinstance(payload, list):
        raise UnexpectedShape(f"response root is {type(payload).__name__}, expected list")

    node: Any = payload
    for index in RESP_REVIEW_NODE:
        if not isinstance(node, list) or index >= len(node):
            # Google answers with a short envelope when a place has no reviews
            # at all; that is data, not breakage.
            return [], None
        node = node[index]
    if node is None:
        return [], None
    if not isinstance(node, list):
        raise UnexpectedShape(f"review node is {type(node).__name__}, expected list")

    reviews = _at(node, RESP_REVIEWS_IDX, []) or []
    token = _at(node, RESP_TOKEN_IDX)
    if not isinstance(reviews, list):
        raise UnexpectedShape(f"review list is {type(reviews).__name__}, expected list")
    return reviews, (token if isinstance(token, str) and token else None)


def _epoch_to_iso(millis: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(millis) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (TypeError, ValueError, OSError):
        return None


def _parse_reviewer(raw: Any) -> dict:
    return {
        "name": _at(raw, 0),
        "avatarUrl": _at(raw, 1),
        "profileUrl": _at(raw, 2),
        "totalReviews": _at(raw, 3),
        "totalPhotos": _at(raw, 4),
        "isLocalGuide": bool(_at(raw, 5)),
    }


def _parse_owner_response(raw: Any) -> dict | None:
    """Owner reply lives at review[4] as [null, relative_time, text, ...]."""
    if not isinstance(raw, list):
        return None
    text = _at(raw, 2)
    relative = _at(raw, 1)
    if not text and not relative:
        return None
    return {
        "text": clean_text(text),
        "relativeTime": relative,
        "reportUrl": next(
            (v for v in raw if isinstance(v, str) and v.startswith("http")), None
        ),
    }


def _parse_reactions(raw: Any) -> tuple[int, dict]:
    """review[47] = [null, [[category, count], ...]].

    Category 3 is the thumbs-up the Maps UI shows as a review's like count;
    the rest are passed through so nothing is lost if Google adds reactions.
    """
    likes = 0
    counts: dict[str, int] = {}
    pairs = _at(raw, 1, []) if isinstance(raw, list) else []
    if isinstance(pairs, list):
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) < 2:
                continue
            category, count = pair[0], pair[1]
            if not isinstance(count, int):
                continue
            counts[str(category)] = count
            if category == REACTION_LIKE_CATEGORY:
                likes = count
    return likes, counts


def _parse_photos(raw: Any) -> list[dict]:
    photos: list[dict] = []
    if not isinstance(raw, list):
        return photos
    for item in raw:
        if not isinstance(item, list):
            continue
        url = _at(item, 0)
        if isinstance(url, str) and url.startswith("http"):
            photos.append({"url": url, "id": _at(item, 3), "aspectRatio": _at(item, 4)})
    return photos


def _parse_attributes(raw: Any) -> list[dict]:
    """review[30]: structured answers such as "When did you visit? -> Weekday"."""
    attributes: list[dict] = []
    if not isinstance(raw, list):
        return attributes
    for entry in raw:
        if not isinstance(entry, list):
            continue
        question = _at(entry, 1)
        answer = None
        block = _at(entry, 2)
        if isinstance(block, list) and block and isinstance(block[0], list):
            first = block[0][0] if block[0] else None
            if isinstance(first, list):
                answer = _at(first, 1)
        if question or answer:
            attributes.append({"question": question, "answer": answer, "label": _at(entry, 5)})
    return attributes


def parse_review(raw: Any) -> dict | None:
    """Turn one positional review array into a flat record."""
    if not isinstance(raw, list):
        return None
    review_id = _at(raw, R_REVIEW_ID)
    if not review_id:
        return None

    time_block = _at(raw, R_TIME, [])
    likes, reaction_counts = _parse_reactions(_at(raw, R_REACTIONS))
    text = clean_text(_at(raw, R_TEXT) or _at(raw, R_TEXT_DISPLAY))
    translated = clean_text(_at(raw, R_TRANSLATED_TEXT) or _at(raw, R_TRANSLATED_DISPLAY))

    return {
        "reviewId": review_id,
        "rating": _at(raw, R_RATING),
        "ratingMax": _at(raw, R_RATING_MAX, 5),
        "text": text,
        "textTranslated": translated,
        "language": _at(raw, R_LANGUAGE),
        "sourceLanguageName": _at(raw, R_SOURCE_LANG_NAME),
        "targetLanguageName": _at(raw, R_TARGET_LANG_NAME),
        "publishedAt": _epoch_to_iso(_at(time_block, 2)),
        "publishedAtTimestamp": _at(time_block, 2),
        "relativeTime": _at(time_block, 0),
        "reviewer": _parse_reviewer(_at(raw, R_REVIEWER)),
        "likesCount": likes,
        "reactionCounts": reaction_counts,
        "ownerResponse": _parse_owner_response(_at(raw, R_OWNER_RESPONSE)),
        "photos": _parse_photos(_at(raw, R_PHOTOS)),
        "attributes": _parse_attributes(_at(raw, R_ATTRIBUTES)),
        "visitedText": _at(raw, R_VISIT_TEXT),
        "visitedMonth": _at(raw, R_VISIT_MONTH),
        "permalink": _at(raw, R_PERMALINK),
        "reportUrl": _at(raw, R_REPORT_URL),
        "sourcePlatform": _at(_at(raw, R_PLATFORM, []), 0, "Google"),
    }


def parse_reviews(raw_reviews: list) -> list[dict]:
    parsed = [parse_review(item) for item in raw_reviews]
    return [record for record in parsed if record]
