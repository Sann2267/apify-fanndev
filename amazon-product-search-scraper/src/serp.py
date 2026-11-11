"""Search-results page parsing: products, badges, prices and pagination."""

import html as htmllib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote_plus, urlparse

from src.constants import DOMAINS, RECORD_PRODUCT

logger = logging.getLogger(__name__)

# A result opens with
#   <div role="listitem" data-asin="B0..." ... data-component-type="s-search-result">
# data-asin PRECEDES data-component-type in the same tag, so splitting on the
# component type alone decapitates the ASIN and lets blocks bleed together.
# Anchoring on all three attributes in order is what keeps items separate.
_ITEM = re.compile(
    r'<div role="listitem"[^>]*data-asin="([A-Z0-9]{10})"[^>]*'
    r'data-component-type="s-search-result"'
)

# Title lives in the h2's aria-label and again in an inner span. There is NO
# separate brand element on the modern SERP -- see extract_brand.
_TITLE_ARIA = re.compile(r'<h2[^>]*aria-label="([^"]{3,400})"')
_TITLE_SPAN = re.compile(r"<h2[^>]*>.*?<span[^>]*>([^<]{3,400})</span>", re.S)
_TITLE_AD_PREFIX = re.compile(r"^\s*Sponsored\s+Ad\s*-\s*", re.I)

# `a-offscreen` is the canonical formatted price. Assembling a-price-whole +
# a-price-fraction picks up neighbouring strike-through prices.
_PRICE = re.compile(r'<span class="a-offscreen">\s*([^<]{2,40})\s*</span>')
# The struck-through "was"/"Typical" price sits inside a-text-price.
_LIST_PRICE = re.compile(
    r'a-text-price[^>]*>\s*<span class="a-offscreen">\s*([^<]{2,40})\s*<', re.S
)

_RATING = re.compile(r"([\d.]+) out of 5 stars")
# The visible review count is ABBREVIATED ("10.5K"). The aria-label carries
# the exact figure, so that is what the actor reports.
_REVIEWS_EXACT = re.compile(r'aria-label="([\d,]+) ratings?"')
_REVIEWS_ABBREV = re.compile(r"s-underline-text[^>]*>\(?([\d.,KM]+)\)?<")

_IMAGE = re.compile(r'<img[^>]*class="s-image"[^>]*src="([^"]+)"')
_SPONSORED_MARKERS = ("puis-sponsored-label-text", "sp-sponsored-result")

_BADGE_TEXT = re.compile(r'<span[^>]*class="[^"]*a-badge-text[^"]*"[^>]*>([^<]{2,40})<')
_BEST_SELLER = re.compile(r"\bBest\s?Seller\b", re.I)
_AMAZONS_CHOICE = re.compile(r"Amazon['’&#x27;]*s\s*Choice", re.I)
_BOUGHT = re.compile(r"([\d,.]+[KM]?)\+?\s*bought in past month", re.I)
_PRIME = re.compile(r'aria-label="Amazon Prime"|icon-prime|a-icon-prime')
_DELIVERY = re.compile(r"(FREE delivery[^<]{0,50}|\$[\d.,]+ delivery[^<]{0,40})")
_SHIPS_TO = re.compile(r"(Ships to [A-Za-z ]{2,30})")

_PAGINATION_NEXT = re.compile(r's-pagination-next[^"]*"', re.I)
_PAGINATION_DISABLED = re.compile(r"s-pagination-next[^>]*s-pagination-disabled", re.I)

_CURRENCY_SYM = re.compile(r"^\s*([A-Z]{3}|[$£€₹¥])")
_AMOUNT = re.compile(r"([\d][\d.,]*)")


class InvalidInput(ValueError):
    """The supplied input could not be used."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value):
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", htmllib.unescape(str(value))).strip()
    return cleaned or None


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


def paginate(url: str, page: int) -> str:
    """Add or replace the page parameter on an arbitrary search URL."""
    if page <= 1:
        return re.sub(r"[&?]page=\d+", "", url)
    if re.search(r"[&?]page=\d+", url):
        return re.sub(r"([&?]page=)\d+", rf"\g<1>{page}", url)
    return f"{url}{'&' if '?' in url else '?'}page={page}"


def normalise_target(raw: str, marketplace: str) -> dict:
    """Turn a keyword or an Amazon search URL into a fetchable target.

    MEASURED: a `/s?` URL only returns products when it carries a `k=`
    keyword. Node-only browse URLs (`/s?rh=n%3A123`, `/s?node=123`, `/b?...`)
    render a browse layout with ZERO search results for anonymous clients, so
    they are rejected up front with an explanation rather than silently
    yielding nothing.
    """
    value = str(raw or "").strip()
    if not value:
        raise InvalidInput("empty target")

    if not re.match(r"^https?://", value, re.I):
        keyword = clean_keyword(value)
        return {"type": "keyword", "label": keyword,
                "url": search_url(marketplace, keyword)}

    parsed = urlparse(value)
    if "amazon." not in (parsed.netloc or "").lower():
        raise InvalidInput(f"{value[:60]!r} is not an amazon.* URL")

    query = parse_qs(parsed.query or "")
    keyword = (query.get("k") or [""])[0].strip()
    if not keyword:
        raise InvalidInput(
            f"{value[:70]!r} has no 'k=' keyword. Amazon serves category and node "
            "URLs (rh=n%3A..., node=..., /b?...) as a browse page with no search "
            "results for logged-out clients, so it cannot be scraped as a SERP. "
            "Add a keyword, e.g. .../s?k=yoga+mat&rh=n%3A3407731"
        )
    return {"type": "url", "label": keyword, "url": value}


def parse_price(text):
    """`$19.99` / `IDR 336,939.57` -> (amount, currency symbol)."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    cleaned = text.replace("\xa0", " ").strip()
    currency = _CURRENCY_SYM.match(cleaned)
    amount = _AMOUNT.search(cleaned)
    value = None
    if amount:
        raw = amount.group(1)
        # The decimal separator is whichever has exactly two digits after it;
        # locales disagree on which of . and , is the thousands mark.
        if re.search(r"[.,]\d{2}$", raw):
            value = raw[:-3].replace(".", "").replace(",", "") + "." + raw[-2:]
        else:
            value = raw.replace(",", "").replace(".", "")
        try:
            value = float(value)
        except ValueError:
            value = None
    return value, (currency.group(1) if currency else None)


def parse_compact_number(text):
    """"10.5K" -> 10500, "1.2M" -> 1200000, "153" -> 153."""
    if not text:
        return None
    cleaned = str(text).replace(",", "").strip().upper()
    match = re.match(r"^([\d.]+)([KM]?)$", cleaned)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return int(value * {"": 1, "K": 1_000, "M": 1_000_000}[match.group(2)])


def clean_title(raw: str) -> str:
    """Unescape and drop Amazon's "Sponsored Ad - " aria-label prefix."""
    return _TITLE_AD_PREFIX.sub("", htmllib.unescape(raw)).strip()


def split_items(page_html: str) -> list[tuple[str, str]]:
    """(asin, block) per search result, in page order."""
    marks = [(m.start(), m.group(1)) for m in _ITEM.finditer(page_html or "")]
    items = []
    for index, (start, asin) in enumerate(marks):
        end = (marks[index + 1][0] if index + 1 < len(marks)
               else min(len(page_html), start + 40_000))
        items.append((asin, page_html[start:end]))
    return items


def has_next_page(page_html: str) -> bool:
    if not page_html or not _PAGINATION_NEXT.search(page_html):
        return False
    return not _PAGINATION_DISABLED.search(page_html)


def extract_brand(title):
    """Amazon's SERP carries NO brand element -- this is a title heuristic.

    Verified across three queries: there is no brand span, no data-brand
    attribute and no brand JSON in the result block; `a-size-base-plus`,
    which older scrapers use for brand, is the TITLE element here. The
    leading token of the title is usually the brand ("Gaiam Yoga Mat...",
    "BLACK+DECKER 12-Cup..."), but it is a guess, not Amazon data, so it is
    reported in `brandGuess` and never in a field claiming to be authoritative.
    """
    value = _text(title)
    if not value:
        return None
    head = re.split(r"[,|\-–—:(]| \d", value, maxsplit=1)[0].strip()
    words = head.split()
    if not words:
        return None
    # Brands are short; a long run of words is a description, not a name.
    guess = " ".join(words[:2]) if len(words) > 1 and len(words[0]) <= 3 else words[0]
    guess = guess.strip(" .,&")
    return guess or None


def parse_item(asin: str, block: str, position: int, context: dict) -> dict:
    title_match = _TITLE_ARIA.search(block) or _TITLE_SPAN.search(block)
    title = clean_title(title_match.group(1)) if title_match else None

    price_match = _PRICE.search(block)
    amount, symbol = parse_price(price_match.group(1) if price_match else None)
    list_match = _LIST_PRICE.search(block)
    list_amount, _ = parse_price(list_match.group(1) if list_match else None)
    # Only a genuinely higher struck-through price is a discount.
    discount = None
    if amount is not None and list_amount is not None and list_amount > amount:
        discount = round((list_amount - amount) / list_amount * 100, 2)

    rating_match = _RATING.search(block)
    exact_reviews = _REVIEWS_EXACT.search(block)
    abbrev_reviews = _REVIEWS_ABBREV.search(block)
    review_count = (
        int(exact_reviews.group(1).replace(",", "")) if exact_reviews
        else parse_compact_number(abbrev_reviews.group(1)) if abbrev_reviews
        else None
    )

    image_match = _IMAGE.search(block)
    bought_match = _BOUGHT.search(block)
    badges = [_text(b) for b in _BADGE_TEXT.findall(block) if _text(b)]
    delivery_match = _DELIVERY.search(block)
    ships_to = _SHIPS_TO.search(block)
    base = DOMAINS[context["marketplace"]]

    return {
        "_input": context["label"],
        "_source": "S1-search-page",
        "_scrapedAt": _now(),
        "recordType": RECORD_PRODUCT,
        "searchTerm": context["label"],
        "targetUrl": context["url"],
        "marketplace": context["marketplace"],
        "page": context["page"],
        "position": position,
        "positionOnPage": context["position_on_page"],
        "asin": asin,
        "title": title,
        # Heuristic, not Amazon data -- see extract_brand.
        "brandGuess": extract_brand(title),
        "price": amount,
        "currency": symbol,
        "listPrice": list_amount,
        "discountPercent": discount,
        "rating": float(rating_match.group(1)) if rating_match else None,
        "reviewCount": review_count,
        "boughtInPastMonth": parse_compact_number(
            bought_match.group(1)) if bought_match else None,
        "isSponsored": any(m in block for m in _SPONSORED_MARKERS),
        "isBestSeller": bool(_BEST_SELLER.search(block)),
        "isAmazonsChoice": bool(_AMAZONS_CHOICE.search(block)),
        "badges": badges or None,
        "isPrime": bool(_PRIME.search(block)),
        "deliveryInfo": _text(delivery_match.group(1)) if delivery_match else None,
        "shipsTo": _text(ships_to.group(1)) if ships_to else None,
        "imageUrl": image_match.group(1) if image_match else None,
        "productUrl": f"{base}/dp/{asin}",
        "_error": None,
        "_errorDetail": None,
    }


def parse_page(page_html: str, context: dict) -> list[dict]:
    records = []
    for index, (asin, block) in enumerate(split_items(page_html)):
        local = dict(context)
        local["position_on_page"] = index + 1
        records.append(
            parse_item(asin, block, context["offset"] + index + 1, local)
        )
    return records
