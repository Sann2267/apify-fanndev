"""Parsing of Amazon's "Customers say" insight widget."""

import base64
import binascii
import html as htmllib
import json
import logging
import re
from datetime import datetime, timezone

from src.constants import (
    BLOCK_MARKERS,
    DOMAINS,
    GAP_SENTIMENTS,
    INSIGHT_RETRY_MIN_REVIEWS,
    MIN_PRODUCT_PAGE_BYTES,
    RECORD_ASPECT,
    RECORD_PRODUCT,
    SENTIMENT_NEGATIVE,
    SENTIMENT_POSITIVE,
)

logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

# PRIMARY aspect signal. Carries sentiment, aspect name AND mention count:
#   aria-label="Positive aspect, quality, 2185 mentions"
_ASPECT_ARIA = re.compile(
    r'aria-label="(Positive|Negative|Mixed) aspect, ([^,"]{1,60}), ([\d,]+) mentions?"'
)

# SECONDARY signal, from the click-tracking id:
#   cr-product-insights-detail-page_button_0_POSITIVE_quality
# It has no mention count, but it survives on localized marketplaces where
# the aria-label is translated and the English regex above cannot match.
_ASPECT_CSA = re.compile(
    r"cr-product-insights-detail-page_button_(\d+)_([A-Z]+)_([^\"'\\<>]{1,60})"
)

# The widget's data is not in the HTML as text -- it is base64 in
# `k-injected k+b64 <payload>` comments whose JSON carries either
# k-data.fragments[].inertText (the overall AI paragraph) or
# k-data.aspectsFlattened (the per-aspect objects).
_KBLOB = re.compile(r"k-injected k\+b64\s+([A-Za-z0-9+/=]{80,})")

# The screen-reader line under each chip, and the only carrier of the
# positive/negative split outside the base64 payload:
#   >634 customers mention writing quality, 617 positive, 17 negative<
_ASPECT_SPLIT = re.compile(
    r">([\d,]+) customers? mention ([^<,]{1,60}), "
    r"([\d,]+) positive, ([\d,]+) negative<"
)

_TITLE = re.compile(r'<span id="productTitle"[^>]*>([^<]{1,500})</span>')
_RATING = re.compile(r"([\d.]+) out of 5 stars")
_REVIEWS = re.compile(r"acrCustomerReviewText[^>]*>\s*\(?([\d,]+)")
_BYLINE = re.compile(r'id="bylineInfo"[^>]*>([^<]{2,120})</a>')


class InvalidInput(ValueError):
    """The supplied input could not be used."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value):
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", htmllib.unescape(str(value))).strip()
    return cleaned or None


def clean_asin(raw) -> str:
    """Normalise and validate one ASIN (or a product URL containing one)."""
    value = str(raw or "").strip()
    if not value:
        raise InvalidInput("empty ASIN")
    if "/" in value or value.lower().startswith("http"):
        found = re.search(r"/(?:dp|gp/product|product)/([A-Z0-9]{10})", value, re.I)
        if not found:
            raise InvalidInput(f"{raw!r} looks like a URL but contains no ASIN")
        value = found.group(1)
    value = value.upper()
    if not ASIN_RE.match(value):
        raise InvalidInput(
            f"{raw!r} is not a valid ASIN (expected 10 letters/digits, got {len(value)})"
        )
    return value


def product_url(marketplace: str, asin: str) -> str:
    return f"{DOMAINS[marketplace]}/dp/{asin}"


def is_blocked(body: str) -> bool:
    """The /dp/ bot wall is an HTTP 200 of ~3.8 KB, so status proves nothing."""
    if not body or len(body) < MIN_PRODUCT_PAGE_BYTES:
        return True
    return any(marker in body[:6000] for marker in BLOCK_MARKERS)


def _decode_blob(blob: str):
    padded = blob + "=" * (-len(blob) % 4)
    try:
        return json.loads(base64.b64decode(padded).decode("utf-8", "replace"))
    except (ValueError, TypeError, binascii.Error):
        return None


def _kdata(body: str):
    """Decoded `k-data` objects from the widget's base64 payloads, in order."""
    for blob in _KBLOB.findall(body or ""):
        decoded = _decode_blob(blob)
        if isinstance(decoded, dict) and isinstance(decoded.get("k-data"), dict):
            yield decoded["k-data"]


def extract_summary(body: str):
    """The "Customers say" AI paragraph, from the base64 fragment payload."""
    for data in _kdata(body):
        fragments = data.get("fragments")
        if not isinstance(fragments, list):
            continue
        parts = [
            _text(fragment.get("inertText"))
            for fragment in fragments
            if isinstance(fragment, dict) and _text(fragment.get("inertText"))
        ]
        if parts:
            return " ".join(parts)
    return None


def _flattened_aspects(body: str) -> list[dict]:
    """The widget's own aspect objects, from the base64 payload.

    A dozen components embed the identical list (MainView, AspectList, one
    AspectButtonRender per chip); the first one found wins. Each object
    carries label, sentiment, mentions, sentimentMentions and summary.
    """
    for data in _kdata(body):
        flattened = data.get("aspectsFlattened")
        if isinstance(flattened, list) and flattened:
            return [entry for entry in flattened if isinstance(entry, dict)]
    return []


def _aspect_details(body: str, flattened: list[dict]) -> dict:
    """Per-aspect positive/negative split and summary sentence, by lowercased name.

    Two independent carriers, both inside the widget:

    * `aspectsFlattened`, which is the only place the per-aspect summary
      sentence exists at all -- it is never rendered as page text.
    * the screen-reader line "634 customers mention writing quality, 617
      positive, 17 negative", used to fill either count the payload lacks.

    `sentimentMentions` is the POSITIVE count for *every* aspect, including
    negative ones: texture on B00XIKPUK4 is sentiment `negative` with
    mentions 392 and sentimentMentions 91, and the page reads "91 positive,
    301 negative". Reading the field as "mentions matching the sentiment"
    would invert the split on exactly the gap aspects this actor is for.
    """
    details = {}

    for entry in flattened:
        label = _text(entry.get("label"))
        if not label or label.lower() in details:
            continue
        mentions, positive = entry.get("mentions"), entry.get("sentimentMentions")
        details[label.lower()] = {
            "positive": positive if isinstance(positive, int) else None,
            "negative": (
                mentions - positive
                if isinstance(mentions, int) and isinstance(positive, int)
                else None
            ),
            "aspectSummary": _text(entry.get("summary")),
        }

    for _, label, positive, negative in _ASPECT_SPLIT.findall(body or ""):
        key = (_text(label) or "").lower()
        if not key:
            continue
        detail = details.setdefault(
            key, {"positive": None, "negative": None, "aspectSummary": None}
        )
        if detail["positive"] is None:
            detail["positive"] = int(positive.replace(",", ""))
        if detail["negative"] is None:
            detail["negative"] = int(negative.replace(",", ""))

    return details


def extract_aspects(body: str) -> list[dict]:
    """Aspects with sentiment, counts and Amazon's per-aspect summary, in page order.

    Three carriers, in descending order of how much they prove:

    1. the aria-labels, which give sentiment, name and mention count;
    2. `aspectsFlattened`, which gives the same three plus the split and the
       summary, and -- being JSON with an English sentiment enum -- keeps
       working where the English aria-label regex cannot;
    3. the click-tracking ids, which carry no count at all.

    A count that was never published stays null rather than becoming 0, or
    every localized row would read as an aspect nobody mentioned.
    """
    flattened = _flattened_aspects(body)
    details = _aspect_details(body, flattened)
    aspects, seen = [], set()

    def add(name, sentiment, mentions):
        key = (_text(name) or "").lower()
        if not key or key in seen:
            return
        seen.add(key)
        detail = details.get(key) or {}
        aspects.append({
            "aspect": _text(name),
            "sentiment": sentiment.upper(),
            "mentions": mentions,
            "positive": detail.get("positive"),
            "negative": detail.get("negative"),
            "aspectSummary": detail.get("aspectSummary"),
        })

    for sentiment, name, mentions in _ASPECT_ARIA.findall(body or ""):
        add(name, sentiment, int(mentions.replace(",", "")))

    for entry in flattened:
        sentiment = _text(entry.get("sentiment"))
        mentions = entry.get("mentions")
        if sentiment:
            add(entry.get("label"), sentiment,
                mentions if isinstance(mentions, int) else None)

    for _, sentiment, name in _ASPECT_CSA.findall(body or ""):
        add(name, sentiment, None)

    return aspects


def parse_insights(body: str, asin: str, marketplace: str) -> dict:
    """Product-level insight record."""
    title = _TITLE.search(body)
    rating = _RATING.search(body)
    reviews = _REVIEWS.search(body)
    byline = _BYLINE.search(body)

    aspects = extract_aspects(body)
    summary = extract_summary(body)
    counted = [a for a in aspects if isinstance(a["mentions"], int)]
    total_mentions = sum(a["mentions"] for a in counted) or None
    gaps = [a for a in aspects if a["sentiment"] in GAP_SENTIMENTS]

    return {
        "_input": asin,
        "_source": "S1-dp-insights",
        "_scrapedAt": _now(),
        "recordType": RECORD_PRODUCT,
        "asin": asin,
        "marketplace": marketplace,
        "productUrl": product_url(marketplace, asin),
        "title": _text(title.group(1)) if title else None,
        "brand": _strip_byline(byline.group(1)) if byline else None,
        "rating": float(rating.group(1)) if rating else None,
        "reviewCount": int(reviews.group(1).replace(",", "")) if reviews else None,
        "aiSummary": summary,
        "hasInsights": bool(aspects or summary),
        "aspectCount": len(aspects) or None,
        "positiveAspectCount": sum(1 for a in aspects if a["sentiment"] == SENTIMENT_POSITIVE),
        "negativeAspectCount": sum(1 for a in aspects if a["sentiment"] == SENTIMENT_NEGATIVE),
        "gapAspectCount": len(gaps),
        "totalMentions": total_mentions,
        # The actionable list: what customers are unhappy or split about.
        "contentGaps": [a["aspect"] for a in gaps] or None,
        "topAspects": [a["aspect"] for a in sorted(
            counted, key=lambda a: a["mentions"], reverse=True)][:5] or None,
        "aspects": aspects or None,
        "_error": None,
        "_errorDetail": None,
    }


def looks_reduced(product: dict) -> bool:
    """True when a page parsed cleanly but is missing a widget it should have.

    Amazon serves some exit IPs a reduced product page. It is not a bot wall
    and `is_blocked` cannot see it: the body is full size, the title, rating
    and review count all parse, and only the insight widget is absent. That
    makes `hasInsights: false` ambiguous -- it means either "this IP got the
    reduced page" or "this product has too few reviews for Amazon to
    summarize", and those want opposite responses.

    The review count is what separates them, and the reduced page still
    carries it. A product with no reviews at all publishes no count, so it
    reads as False here and is never retried.
    """
    if product.get("hasInsights"):
        return False
    reviews = product.get("reviewCount")
    return isinstance(reviews, int) and reviews >= INSIGHT_RETRY_MIN_REVIEWS


def aspect_records(product: dict) -> list[dict]:
    """One row per aspect, ranked by mentions within the product.

    Emitted alongside the product row so the dataset can be sorted and
    filtered by sentiment directly, which is how a copywriter uses it. The
    positive/negative split is what makes MIXED actionable: two aspects both
    labelled MIXED can be 58/52 and 18/36.
    """
    aspects = product.get("aspects") or []
    total = product.get("totalMentions")
    ranked = sorted(
        aspects,
        key=lambda a: (a["mentions"] is not None, a["mentions"] or 0),
        reverse=True,
    )
    rows = []
    for index, aspect in enumerate(ranked, start=1):
        mentions = aspect["mentions"]
        rows.append({
            "_input": product["asin"],
            "_source": product["_source"],
            "_scrapedAt": product["_scrapedAt"],
            "recordType": RECORD_ASPECT,
            "asin": product["asin"],
            "marketplace": product["marketplace"],
            "productUrl": product["productUrl"],
            "title": product["title"],
            "brand": product["brand"],
            "aspect": aspect["aspect"],
            "sentiment": aspect["sentiment"],
            "mentions": mentions,
            "positive": aspect.get("positive"),
            "negative": aspect.get("negative"),
            "aspectSummary": aspect.get("aspectSummary"),
            "mentionRank": index,
            "mentionSharePercent": (
                round(mentions / total * 100, 2)
                if isinstance(mentions, int) and total else None
            ),
            "isContentGap": aspect["sentiment"] in GAP_SENTIMENTS,
            "rating": product["rating"],
            "reviewCount": product["reviewCount"],
            "_error": None,
            "_errorDetail": None,
        })
    return rows


def _strip_byline(raw):
    """"Visit the Nutricost Store" / "Brand: X" -> "Nutricost"."""
    value = _text(raw) or ""
    value = re.sub(r"^\s*(Visit the|Brand:)\s*", "", value, flags=re.I)
    value = re.sub(r"\s*Store\s*$", "", value, flags=re.I)
    return value or None
