"""Product-page parsing, Buy Box extraction, variations and change detection."""

import html as htmllib
import json
import logging
import re
from datetime import datetime, timezone

from src.constants import (
    AMAZON_MERCHANT_ID,
    BLOCK_MARKERS,
    CHANGE_BACK_IN_STOCK,
    CHANGE_BUYBOX_FLIP,
    CHANGE_NEW,
    CHANGE_OUT_OF_STOCK,
    CHANGE_PRICE_DOWN,
    CHANGE_PRICE_UP,
    CHANGE_UNCHANGED,
    DOMAINS,
    MARKETPLACE_CURRENCY,
    MIN_PRODUCT_PAGE_BYTES,
    RECORD_PRODUCT,
)

logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

_TITLE = re.compile(r'<span id="productTitle"[^>]*>([^<]{1,500})</span>')
# Price must come from a CANONICAL container, never from the first
# `a-offscreen` on the page.
#
# Measured: on pages where Amazon withholds the Buy Box (~half of anonymous
# requests) none of these containers exist at all, yet the page still
# contains many `a-offscreen` spans belonging to *related products and other
# variants*. Taking the first one gave B0BJLBD427 a price of $2489.00 on one
# render and $102.95 on another, when the product itself had no price served.
# Wrong-but-plausible prices are worse than nulls for a repricing tool, so a
# product with no canonical price reports `null`.
_PRICE_SOURCES = (
    re.compile(r'"priceAmount"\s*:\s*([\d.]+)'),
    re.compile(r'id="corePrice_feature_div".{0,1500}?a-offscreen">\s*([^<]{2,40})\s*<', re.S),
    re.compile(r'twister-plus-price-data-price"\s+value="([\d.]+)"'),
    re.compile(r'"displayPrice"\s*:\s*"([^"]{2,40})"'),
)
_BYLINE = re.compile(r'id="bylineInfo"[^>]*>([^<]{2,120})</a>')
_RATING = re.compile(r"([\d.]+) out of 5 stars")
# Amazon renders the count parenthesised: "(10,765)".
_REVIEWS = re.compile(r"acrCustomerReviewText[^>]*>\s*\(?([\d,]+)")
_AVAIL = re.compile(r'id="availability".{0,300}?<span[^>]*>\s*([^<]{3,80})', re.S)
_BSR = re.compile(r"Best Sellers Rank.{0,300}?#([\d,]+)\s+in\s+([A-Za-z &,\-]{3,60})", re.S)

# Two independent seller signals, measured over 8 diverse ASINs:
#   hidden merchantID input        4/8
#   visible sellerProfileTriggerId 3/8
# They do not always co-occur, so both are tried. See CRAWLING_METHOD.md --
# roughly 40-50% of anonymous /dp/ responses omit the Buy Box block
# entirely, deterministically per ASIN.
_MERCHANT_ID = re.compile(r'name="merchantID"\s+value="([A-Z0-9]{6,20})"')
_SELLER_LINK_ID = re.compile(r"seller=([A-Z0-9]{10,20})")
_SELLER_NAME = re.compile(r'id="sellerProfileTriggerId"[^>]*>\s*([^<]{2,80})\s*<')
_SOLD_BY = re.compile(
    r"Sold by.{0,500}?offer-display-feature-text-message[^>]*>\s*([^<]{2,80})\s*<", re.S
)
_SHIPS_FROM = re.compile(
    r"Ships from.{0,600}?offer-display-feature-text-message[^>]*>\s*([^<]{2,80})\s*<", re.S
)
_RETURNS = re.compile(
    r"(\d+ days? returnable|Returnable until [^<]{4,40}|Non-returnable|FREE Returns)"
)
_ATC = re.compile(r"add-to-cart-button|submit\.add-to-cart")
_IMAGE_HI = re.compile(r'"hiRes"\s*:\s*"(https[^"]{10,400})"')
_IMAGE_LANDING = re.compile(r'id="landingImage"[^>]*src="([^"]{10,400})"')
_FEATURES = re.compile(r'id="feature-bullets".*?</div>', re.S)
_BULLET = re.compile(r'<span[^>]*class="a-list-item"[^>]*>\s*([^<]{3,300})\s*</span>')

_PARENT_ASIN = re.compile(r'"parentAsin"\s*:\s*"([A-Z0-9]{10})"')
_CURRENT_ASIN = re.compile(r'"currentAsin"\s*:\s*"([A-Z0-9]{10})"')
_DIM_LABELS = re.compile(r'"variationDisplayLabels"\s*:\s*(\{[^{}]{0,400}\})')
_DIM_DATA = re.compile(r'"dimensionValuesDisplayData"\s*:\s*(\{.*?\})\s*,\s*"', re.S)
_CHILD_PAIR = re.compile(r'"([A-Z0-9]{10})"\s*:\s*(\[[^\]]*\])')

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
    """A /dp/ block arrives as HTTP 200 with a short body -- status is useless."""
    if not body or len(body) < MIN_PRODUCT_PAGE_BYTES:
        return True
    head = body[:6000]
    return any(marker in head for marker in BLOCK_MARKERS)


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
        # The decimal separator is whichever one has exactly two digits after
        # it; locales disagree on which of . and , is the thousands mark.
        if re.search(r"[.,]\d{2}$", raw):
            value = raw[:-3].replace(".", "").replace(",", "") + "." + raw[-2:]
        else:
            value = raw.replace(",", "").replace(".", "")
        try:
            value = float(value)
        except ValueError:
            value = None
    return value, (currency.group(1) if currency else None)


def extract_price(body: str):
    """(amount, currency) from a canonical price container, else (None, None).

    Returning None is the correct answer for a page that did not carry this
    product's price -- see `_PRICE_SOURCES`.
    """
    for pattern in _PRICE_SOURCES:
        match = pattern.search(body)
        if not match:
            continue
        amount, symbol = parse_price(match.group(1))
        if amount is not None:
            # `priceAmount` and the twister value are bare numbers with no
            # symbol; fall back to the marketplace's displayed symbol.
            if symbol is None:
                display = re.search(r'"displayPrice"\s*:\s*"\s*([A-Z]{3}|[$£€₹¥])', body)
                symbol = display.group(1) if display else None
            return amount, symbol
    return None, None


def parse_buybox(body: str) -> dict:
    """Seller / fulfilment / returns for the current Buy Box winner.

    Roughly 40-50% of anonymous responses omit this block entirely, so the
    caller MUST distinguish "no Buy Box data served" from "Amazon is the
    seller" -- hence `available`.
    """
    merchant = _MERCHANT_ID.search(body)
    seller_id = merchant.group(1) if merchant else None
    if not seller_id:
        link = _SELLER_LINK_ID.search(body)
        seller_id = link.group(1) if link else None

    name = _SELLER_NAME.search(body) or _SOLD_BY.search(body)
    seller_name = _text(name.group(1)) if name else None
    if not seller_name and seller_id == AMAZON_MERCHANT_ID:
        seller_name = "Amazon.com"

    ships = _SHIPS_FROM.search(body)
    returns = _RETURNS.search(body)

    return {
        "available": bool(seller_id or seller_name),
        "sellerId": seller_id,
        "sellerName": seller_name,
        "isAmazonSeller": (seller_id == AMAZON_MERCHANT_ID) if seller_id else None,
        "shipsFrom": _text(ships.group(1)) if ships else None,
        "returnPolicy": _text(returns.group(1)) if returns else None,
        "hasAddToCart": bool(_ATC.search(body)),
    }


def _safe_list(raw):
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def parse_variations(body: str, asin: str) -> dict:
    """Parent/child variation family from the twister payload."""
    parent = _PARENT_ASIN.search(body)
    current = _CURRENT_ASIN.search(body)

    labels = {}
    label_match = _DIM_LABELS.search(body)
    if label_match:
        try:
            loaded = json.loads(label_match.group(1))
            labels = loaded if isinstance(loaded, dict) else {}
        except (ValueError, TypeError):
            labels = {}

    children, dimensions = [], {}
    data_match = _DIM_DATA.search(body)
    if data_match:
        raw = data_match.group(1)
        parsed = None
        try:
            loaded = json.loads(raw)
            parsed = loaded if isinstance(loaded, dict) else None
        except (ValueError, TypeError):
            parsed = None
        if parsed is None:
            # The twister blob is large and sometimes truncated by the
            # surrounding regex; fall back to pair-scraping rather than
            # losing the whole variation family.
            parsed = {k: _safe_list(v) for k, v in _CHILD_PAIR.findall(raw)}
        for child, values in parsed.items():
            if not ASIN_RE.match(str(child)):
                continue
            children.append(child)
            if isinstance(values, list):
                cleaned = [_text(v) for v in values if _text(v)]
                if cleaned:
                    dimensions[child] = cleaned

    return {
        "parentAsin": parent.group(1) if parent else None,
        "currentAsin": current.group(1) if current else asin,
        "dimensionLabels": [_text(v) for v in labels.values() if _text(v)] or None,
        "childAsins": children or None,
        "variationCount": len(children) or None,
        "childDimensions": dimensions or None,
    }


def _strip_byline(raw):
    """"Visit the Nutricost Store" / "Brand: X" -> "Nutricost"."""
    value = _text(raw) or ""
    value = re.sub(r"^\s*(Visit the|Brand:)\s*", "", value, flags=re.I)
    value = re.sub(r"\s*Store\s*$", "", value, flags=re.I)
    return value or None


def in_stock(availability, has_cart: bool, offer_served: bool = True):
    """Tri-state: True / False / None when Amazon served no signal at all.

    An explicit availability line is always trusted. The add-to-cart button
    is only trusted when Amazon actually served the offer block: on the
    reduced page variant a cart button is still rendered (it belongs to the
    variant picker) while no price or seller is served, so treating it as
    proof of stock asserted "in stock" for every product whose offer was
    withheld -- 4 of 10 ASINs in testing.
    """
    if availability:
        lowered = availability.lower()
        if any(bad in lowered for bad in
               ("unavailable", "out of stock", "not available", "sign in to see")):
            return False
        if any(good in lowered for good in
               ("in stock", "available", "left in stock", "order soon")):
            return True
    if has_cart and offer_served:
        return True
    return None


def parse_product(body: str, asin: str, marketplace: str, want_variations: bool = True) -> dict:
    title = _TITLE.search(body)
    amount, symbol = extract_price(body)
    byline = _BYLINE.search(body)
    rating = _RATING.search(body)
    reviews = _REVIEWS.search(body)
    avail = _AVAIL.search(body)
    bsr = _BSR.search(body)
    image = _IMAGE_HI.search(body) or _IMAGE_LANDING.search(body)

    features = []
    block = _FEATURES.search(body)
    if block:
        features = [
            _text(b) for b in _BULLET.findall(block.group(0))
            if _text(b) and "make sure this fits" not in b.lower()
        ][:12]

    buybox = parse_buybox(body)
    availability = _text(avail.group(1)) if avail else None
    variations = parse_variations(body, asin) if want_variations else {}
    if amount is not None and symbol is None:
        symbol = MARKETPLACE_CURRENCY.get(marketplace)

    return {
        "_input": asin,
        "_source": "S1-dp-page",
        "_scrapedAt": _now(),
        "recordType": RECORD_PRODUCT,
        "asin": asin,
        "marketplace": marketplace,
        "productUrl": product_url(marketplace, asin),
        "title": _text(title.group(1)) if title else None,
        "brand": _strip_byline(byline.group(1)) if byline else None,
        "price": amount,
        "currency": symbol,
        "availability": availability,
        "inStock": in_stock(availability, buybox["hasAddToCart"], buybox["available"]),
        # Anonymous product pages advertise the New offer; used/refurbished
        # offers live behind the all-offers panel, which Amazon does not
        # serve to anonymous HTTP clients (see CRAWLING_METHOD.md).
        "condition": "New" if amount is not None else None,
        "rating": float(rating.group(1)) if rating else None,
        "reviewCount": int(reviews.group(1).replace(",", "")) if reviews else None,
        "bestSellersRank": int(bsr.group(1).replace(",", "")) if bsr else None,
        "bestSellersCategory": _text(bsr.group(2)) if bsr else None,
        "imageUrl": image.group(1) if image else None,
        "featureBullets": features or None,
        # --- Buy Box ------------------------------------------------------
        "buyBoxDataAvailable": buybox["available"],
        "buyBoxSellerId": buybox["sellerId"],
        "buyBoxSellerName": buybox["sellerName"],
        "buyBoxIsAmazon": buybox["isAmazonSeller"],
        "shipsFrom": buybox["shipsFrom"],
        "returnPolicy": buybox["returnPolicy"],
        "hasAddToCart": buybox["hasAddToCart"],
        # --- variations ---------------------------------------------------
        "parentAsin": variations.get("parentAsin"),
        "childAsins": variations.get("childAsins"),
        "variationCount": variations.get("variationCount"),
        "variationDimensions": variations.get("dimensionLabels"),
        "_error": None,
        "_errorDetail": None,
    }


def snapshot_key(record: dict) -> dict:
    """The minimal shape stored between runs for change detection."""
    return {
        "price": record.get("price"),
        "buyBoxSellerId": record.get("buyBoxSellerId"),
        "buyBoxSellerName": record.get("buyBoxSellerName"),
        "inStock": record.get("inStock"),
        "scrapedAt": record.get("_scrapedAt"),
    }


def detect_changes(record: dict, previous) -> dict:
    """Compare against the previous run's snapshot for this ASIN."""
    if not previous:
        return {
            "changeType": CHANGE_NEW, "changes": None, "previousPrice": None,
            "previousSellerId": None, "priceDelta": None, "priceDeltaPercent": None,
            "previousScrapedAt": None,
        }

    changes = []
    old_price, new_price = previous.get("price"), record.get("price")
    delta = delta_pct = None
    if isinstance(old_price, (int, float)) and isinstance(new_price, (int, float)):
        delta = round(new_price - old_price, 2)
        if old_price:
            delta_pct = round(delta / old_price * 100, 2)
        if delta > 0:
            changes.append(CHANGE_PRICE_UP)
        elif delta < 0:
            changes.append(CHANGE_PRICE_DOWN)

    old_seller, new_seller = previous.get("buyBoxSellerId"), record.get("buyBoxSellerId")
    # Only a real seller-to-different-seller move counts. Amazon omitting the
    # Buy Box block this run is a rendering gap, not a Buy Box flip -- calling
    # it one would fire false alerts on roughly half of all ASINs.
    if old_seller and new_seller and old_seller != new_seller:
        changes.append(CHANGE_BUYBOX_FLIP)

    old_stock, new_stock = previous.get("inStock"), record.get("inStock")
    if old_stock is False and new_stock is True:
        changes.append(CHANGE_BACK_IN_STOCK)
    elif old_stock is True and new_stock is False:
        changes.append(CHANGE_OUT_OF_STOCK)

    return {
        "changeType": changes[0] if changes else CHANGE_UNCHANGED,
        "changes": changes or None,
        "previousPrice": old_price,
        "previousSellerId": old_seller,
        "priceDelta": delta,
        "priceDeltaPercent": delta_pct,
        "previousScrapedAt": previous.get("scrapedAt"),
    }
