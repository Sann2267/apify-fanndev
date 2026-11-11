"""Search-page parsing, sponsored detection and advertiser aggregation."""

import html as htmllib
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote_plus

from src.constants import (
    DOMAINS,
    RECORD_AD,
    RECORD_ORGANIC,
    RECORD_SUMMARY,
    SLOT_MID,
    SLOT_TOP,
)

logger = logging.getLogger(__name__)

# Each search result opens with `<div role="listitem" data-asin="..." ...
# data-component-type="s-search-result">`. Anchoring on all three attributes
# in order is what keeps blocks from bleeding into one another -- splitting
# on `data-component-type` alone drops the ASIN (it appears earlier in the
# same tag) and produced false sponsored counts during recon.
_ITEM = re.compile(
    r'<div role="listitem"[^>]*data-asin="([A-Z0-9]{10})"[^>]*'
    r'data-component-type="s-search-result"'
)

# Verified against the live page: the per-result sponsored label. Other
# "sponsored" strings on the page (AdHolder, s-sponsored-label in feedback
# widgets) sit OUTSIDE the result items and must not be counted.
_SPONSORED_MARKERS = ("puis-sponsored-label-text", "sp-sponsored-result")

# `a-offscreen` is the canonical, fully-formatted price. Assembling
# a-price-whole + a-price-fraction is fragile and picked up strike-through
# prices from neighbouring markup during recon.
_PRICE = re.compile(r'<span class="a-offscreen">\s*([^<]{2,40})</span>')
_TITLE_ARIA = re.compile(r'<h2[^>]*aria-label="([^"]{3,300})"')
# Amazon prefixes the aria-label of a sponsored tile with "Sponsored Ad - ".
# That is the ad label, not part of the product name, so it is stripped --
# otherwise every ad row's title differs from the same product's organic row
# and grouping by title breaks.
_TITLE_AD_PREFIX = re.compile(r"^\s*Sponsored\s+Ad\s*-\s*", re.I)
_TITLE_SPAN = re.compile(r"<h2[^>]*>.*?<span[^>]*>([^<]{3,300})</span>", re.S)
_RATING = re.compile(r"([\d.]+) out of 5 stars")
_REVIEWS = re.compile(r'aria-label="([\d,]+) ratings?"')
_IMAGE = re.compile(r'<img[^>]*class="s-image"[^>]*src="([^"]+)"')
_PRIME = re.compile(r'aria-label="Amazon Prime"|s-prime|"isPrime":true')
_CURRENCY = re.compile(r"^\s*([A-Z]{3}|[$£€₹¥])")
_AMOUNT = re.compile(r"([\d][\d.,]*)")


class InvalidInput(ValueError):
    """The input could not be used."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_keyword(raw: str) -> str:
    value = " ".join(str(raw or "").split())
    if not value:
        raise InvalidInput("empty keyword")
    if len(value) > 200:
        raise InvalidInput(f"{raw[:40]!r}... is too long to be a search keyword")
    return value


def search_url(marketplace: str, keyword: str, page: int = 1) -> str:
    base = DOMAINS[marketplace]
    url = f"{base}/s?k={quote_plus(keyword)}"
    return url if page <= 1 else f"{url}&page={page}"


def parse_price(text):
    """`$19.99` / `IDR 336,939.57` -> (amount, currency)."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    cleaned = text.replace("\xa0", " ").strip()
    currency = _CURRENCY.match(cleaned)
    amount = _AMOUNT.search(cleaned)
    value = None
    if amount:
        raw = amount.group(1)
        # Thousands separators differ by locale; the decimal part is
        # whichever separator has exactly two digits after it.
        if re.search(r"[.,]\d{2}$", raw):
            value = raw[:-3].replace(".", "").replace(",", "") + "." + raw[-2:]
        else:
            value = raw.replace(",", "").replace(".", "")
        try:
            value = float(value)
        except ValueError:
            value = None
    return value, (currency.group(1) if currency else None)


def clean_title(raw: str) -> str:
    """Unescape and drop Amazon's "Sponsored Ad - " aria-label prefix."""
    return _TITLE_AD_PREFIX.sub("", htmllib.unescape(raw)).strip()


def slot_band(position: int) -> str:
    if position <= SLOT_TOP:
        return "TOP"
    return "MID" if position <= SLOT_MID else "LOWER"


def split_items(page_html: str) -> list[tuple[str, str]]:
    """(asin, block) per search result, in page order."""
    marks = [(m.start(), m.group(1)) for m in _ITEM.finditer(page_html or "")]
    items = []
    for index, (start, asin) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else min(len(page_html), start + 40_000)
        items.append((asin, page_html[start:end]))
    return items


def is_sponsored(block: str) -> bool:
    return any(marker in block for marker in _SPONSORED_MARKERS)


def parse_item(asin: str, block: str, position: int, context: dict) -> dict:
    title_match = _TITLE_ARIA.search(block) or _TITLE_SPAN.search(block)
    price_match = _PRICE.search(block)
    rating_match = _RATING.search(block)
    reviews_match = _REVIEWS.search(block)
    image_match = _IMAGE.search(block)
    amount, currency = parse_price(price_match.group(1) if price_match else None)
    sponsored = is_sponsored(block)
    base = DOMAINS[context["marketplace"]]

    return {
        "_input": context["keyword"],
        "_source": "S1-search-page",
        "_scrapedAt": _now(),
        "recordType": RECORD_AD if sponsored else RECORD_ORGANIC,
        "keyword": context["keyword"],
        "marketplace": context["marketplace"],
        "sampleIndex": context["sample"],
        "isSponsored": sponsored,
        "position": position,
        "slotBand": slot_band(position) if sponsored else None,
        "asin": asin,
        "title": clean_title(title_match.group(1)) if title_match else None,
        "price": amount,
        "currency": currency,
        "rating": float(rating_match.group(1)) if rating_match else None,
        "reviewCount": int(reviews_match.group(1).replace(",", "")) if reviews_match else None,
        "imageUrl": image_match.group(1) if image_match else None,
        "productUrl": f"{base}/dp/{asin}",
        "isPrime": bool(_PRIME.search(block)),
    }


def summary_record(records: list, context: dict, samples: int) -> dict:
    """Per-keyword advertiser roll-up -- the "who is bidding hardest" answer.

    Emitted even when nothing was sponsored, because a keyword with no ads
    is itself a finding and a silently missing row looks like a failure.
    """
    ads = [r for r in records if r["isSponsored"]]
    total = len(records)
    positions = sorted(r["position"] for r in ads)
    advertisers = Counter(r["asin"] for r in ads)
    prices = [r["price"] for r in ads if isinstance(r.get("price"), (int, float))]
    ratings = [r["rating"] for r in ads if isinstance(r.get("rating"), (int, float))]

    return {
        "_input": context["keyword"],
        "_source": "S2-aggregate",
        "_scrapedAt": _now(),
        "recordType": RECORD_SUMMARY,
        "keyword": context["keyword"],
        "marketplace": context["marketplace"],
        "samplesTaken": samples,
        "totalResults": total,
        "sponsoredCount": len(ads),
        "organicCount": total - len(ads),
        "sponsoredSharePercent": round(len(ads) / total * 100, 2) if total else None,
        "sponsoredPositions": positions,
        "topSlotAdCount": sum(1 for p in positions if p <= SLOT_TOP),
        "uniqueAdvertisedAsins": len(advertisers),
        # An ASIN appearing across several samples is bidding persistently,
        # not just winning one impression.
        "mostPersistentAsins": [
            {"asin": asin, "appearances": count}
            for asin, count in advertisers.most_common(10)
        ],
        "avgAdPrice": round(sum(prices) / len(prices), 2) if prices else None,
        "avgAdRating": round(sum(ratings) / len(ratings), 2) if ratings else None,
    }


def parse_page(page_html: str, context: dict) -> list[dict]:
    return [
        parse_item(asin, block, index + 1, context)
        for index, (asin, block) in enumerate(split_items(page_html))
    ]
