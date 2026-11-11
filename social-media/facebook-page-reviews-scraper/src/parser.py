"""Parse a Facebook page's reviews tab.

Two different things live on that tab and they are parsed separately:

1. **The rating summary**, a single node:
   `profile_rating_reviews.title.text` -> `"30% recommend (12,651 reviews)"`.
   Facebook retired star ratings for pages in favour of a recommend / do not
   recommend vote, so this percentage *is* the rating -- there is no 4.3-out-of-5
   hiding anywhere, and this actor does not invent one.

2. **The reviews themselves**, one story each. A review's story node carries
   `post_id`, `title` and `actors` together, where the title is the sentence
   Facebook renders above the review:
       "Mike Phipps  doesn't recommend Domino's Pizza."
   That sentence is the only place the recommend/do-not-recommend vote appears
   in the payload -- there is no boolean field -- so it is parsed from the text,
   and `isRecommended` is left null when the sentence does not match rather than
   defaulting to one of the two answers.
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import find_nodes, iter_json_blocks, og_tag, walk

# "30% recommend (12,651 reviews)" / "100% recommend (7 reviews)"
SUMMARY = re.compile(
    r"(\d[\d.,]*)\s*%\s*recommend\s*\(([\d.,]+)\s*review", re.I
)
NOT_RECOMMEND = re.compile(r"do(?:es)?\s*n[o']?t\s+recommend", re.I)
RECOMMENDS = re.compile(r"\brecommends\b", re.I)
PAGE_SLUG = re.compile(r"facebook\.com/(?:pg/)?([^/?#]+)", re.I)
RESERVED = {"profile.php", "people", "groups", "events", "marketplace", "watch", "ads"}


def page_ref(value: str) -> str | None:
    """Reduce a page URL or slug to the bare vanity slug."""
    value = (value or "").strip()
    if not value:
        return None
    match = PAGE_SLUG.match(value) or PAGE_SLUG.search(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    if not value or value.lower() in RESERVED:
        return None
    return value


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


def parse_summary(html: str) -> dict:
    """The page's recommendation summary, plus its name and id."""
    out: dict[str, Any] = {
        "pageName": None,
        "pageId": None,
        "ratingSummaryText": None,
        "recommendPercent": None,
        "reviewCount": None,
        "reviewsEnabled": False,
    }

    raw_name = og_tag(html, "og:title")
    if raw_name:
        out["pageName"] = re.sub(r"\s*\|\s*Facebook\s*$", "", raw_name).strip() or None

    for block in iter_json_blocks(html):
        for node in walk(block):
            summary = node.get("profile_rating_reviews")
            if isinstance(summary, dict):
                text = (summary.get("title") or {}).get("text")
                if isinstance(text, str) and text.strip():
                    out["ratingSummaryText"] = text.strip()
                    out["reviewsEnabled"] = True
                    match = SUMMARY.search(text)
                    if match:
                        try:
                            out["recommendPercent"] = float(match.group(1).replace(",", ""))
                        except ValueError:
                            pass
                        out["reviewCount"] = _int(match.group(2))
            if out["pageId"] is None and node.get("__typename") in ("User", "Page"):
                candidate = node.get("id")
                if isinstance(candidate, str) and candidate.isdigit() and len(candidate) >= 8:
                    out["pageId"] = candidate
    return out


NODE_ID_TAIL = re.compile(r"(?:^|:)(\d{8,})$")


def _post_id_from_node_id(node_id: str) -> str | None:
    """Recover the post id from one of Facebook's base64 story ids."""
    if len(node_id) < 12:
        return None
    try:
        decoded = base64.b64decode(node_id + "==", validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None
    if not decoded.startswith(("S:", "feedback:")):
        return None
    match = NODE_ID_TAIL.search(decoded)
    return match.group(1) if match else None


def _vote(title: str | None) -> bool | None:
    """Read the recommend vote out of Facebook's own sentence.

    Order matters: "doesn't recommend" also contains "recommend", so the negative
    is tested first. A sentence in another language returns None rather than a
    coin flip, which is why the actor requests en-US.
    """
    if not title:
        return None
    if NOT_RECOMMEND.search(title):
        return False
    if RECOMMENDS.search(title):
        return True
    return None


def _blank_review(post_id: str) -> dict:
    return {
        "reviewId": post_id,
        "reviewTitle": None,
        "isRecommended": None,
        "reviewerName": None,
        "reviewerId": None,
        "reviewerUrl": None,
        "reviewText": None,
        "createdAt": None,
        "createdAtIso": None,
        "reactionCount": None,
        "commentCount": None,
        "reviewUrl": None,
        "tags": [],
    }


def parse_reviews(payload: Any) -> list[dict]:
    """Every review in a payload, assembled by the post id its nodes name.

    A review is no more a single object than a group post is. The recommend
    sentence and the reviewer sit on one node, the written body on another, the
    timestamp and permalink on a third. What they share is the post id -- either
    outright as `post_id`, or inside the base64 `id` every story node carries:

        UzpfSTYxNTUyOTY1OTQ0MzI2OjEyMjI1ODIyNjM2ODA5ODg2NDoxMjI...
            -> "S:_I61552965944326:122258226368098864:122258226368098864"

    So the parser files each field under the post it names. Reading only the
    node that owns the title returns every review with an empty body, because
    the body is not on that node.
    """
    reviews: dict[str, dict] = {}

    def slot(post_id: str) -> dict:
        return reviews.setdefault(post_id, _blank_review(post_id))

    for node in walk(payload):
        post_id = None
        if isinstance(node.get("post_id"), str):
            post_id = node["post_id"]
        elif isinstance(node.get("id"), str):
            post_id = _post_id_from_node_id(node["id"])
        if not post_id:
            continue

        review = slot(post_id)

        title = node.get("title")
        if review["reviewTitle"] is None and isinstance(title, dict):
            text = title.get("text")
            if isinstance(text, str) and "recommend" in text.lower():
                review["reviewTitle"] = text
                review["isRecommended"] = _vote(text)

        actors = node.get("actors")
        if review["reviewerName"] is None and isinstance(actors, list) and actors:
            actor = actors[0]
            if isinstance(actor, dict) and actor.get("name"):
                review["reviewerName"] = actor.get("name")
                review["reviewerId"] = actor.get("id")
                review["reviewerUrl"] = actor.get("url")

        message = node.get("message")
        if review["reviewText"] is None and isinstance(message, dict):
            text = message.get("text")
            if isinstance(text, str) and text.strip():
                review["reviewText"] = text
        if review["createdAt"] is None and isinstance(node.get("creation_time"), int):
            review["createdAt"] = node["creation_time"]
        if review["reviewUrl"] is None and isinstance(node.get("permalink_url"), str):
            review["reviewUrl"] = node["permalink_url"]

        for inner in walk(node):
            if review["reactionCount"] is None and "i18n_reaction_count" in inner:
                review["reactionCount"] = _int(inner.get("i18n_reaction_count"))
            if review["commentCount"] is None and isinstance(inner.get("comments"), dict):
                review["commentCount"] = _int(inner["comments"].get("total_count"))
            attachment = inner.get("attachment")
            if not review["tags"] and isinstance(attachment, dict) and isinstance(
                attachment.get("tags"), list
            ):
                review["tags"] = [t for t in attachment["tags"] if isinstance(t, str)]

    out = []
    for review in reviews.values():
        # A node that names a post but carries no review content is a tracking
        # or layout wrapper, not somebody's review.
        if not (review["reviewTitle"] or review["reviewText"]):
            continue
        review["createdAtIso"] = _iso(review["createdAt"])
        out.append(review)
    return out


def parse_reviews_html(html: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for block in iter_json_blocks(html):
        for review in parse_reviews(block):
            if review["reviewId"] not in seen:
                seen.add(review["reviewId"])
                out.append(review)
    return out


def next_cursor(payload: Any) -> str | None:
    for node in find_nodes(payload, "page_info"):
        info = node["page_info"]
        if isinstance(info, dict) and info.get("has_next_page") and info.get("end_cursor"):
            return info["end_cursor"]
    return None


def matches_filters(review: dict, filters: dict) -> bool:
    if filters.get("onlyRecommended") and review.get("isRecommended") is not True:
        return False
    if filters.get("onlyNotRecommended") and review.get("isRecommended") is not False:
        return False
    if filters.get("onlyWithText") and not (review.get("reviewText") or "").strip():
        return False
    needle = (filters.get("textContains") or "").strip().lower()
    if needle and needle not in (review.get("reviewText") or "").lower():
        return False
    since = filters.get("postedAfterEpoch")
    if isinstance(since, int):
        stamp = review.get("createdAt")
        if not isinstance(stamp, int) or stamp < since:
            return False
    return True


def summarise(reviews: Iterable[dict]) -> dict:
    reviews = list(reviews)
    positive = sum(1 for r in reviews if r.get("isRecommended") is True)
    negative = sum(1 for r in reviews if r.get("isRecommended") is False)
    unknown = len(reviews) - positive - negative
    with_text = sum(1 for r in reviews if (r.get("reviewText") or "").strip())
    newest = max((r["createdAt"] for r in reviews if r.get("createdAt")), default=None)
    oldest = min((r["createdAt"] for r in reviews if r.get("createdAt")), default=None)
    return {
        "reviewsCollected": len(reviews),
        "recommended": positive,
        "notRecommended": negative,
        "voteUnreadable": unknown,
        "reviewsWithText": with_text,
        # Computed from what was collected, which is a sample -- the page's own
        # figure is reported separately as recommendPercent.
        "sampleRecommendPercent": (
            round(100.0 * positive / (positive + negative), 1)
            if (positive + negative)
            else None
        ),
        "newestReviewIso": _iso(newest),
        "oldestReviewIso": _iso(oldest),
    }
