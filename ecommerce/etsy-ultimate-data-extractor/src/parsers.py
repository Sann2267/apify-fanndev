"""Parsers for Etsy's server-rendered HTML.

Etsy renders everything this actor needs on the server, in three layers:

  schema.org JSON-LD   the trustworthy layer. Listing pages carry a Product
                       (description, image set, category path, brand, price
                       range, stock, availability, aggregate rating) plus a
                       BreadcrumbList and an FAQPage; shop pages carry an
                       Organization and an ItemList of the whole visible
                       catalogue. Parsed first wherever it exists.

  wt-* Collage markup  Etsy's design system. Stable class names
                       (`v2-listing-card`, `shop2-review-attribution`,
                       `sb-shop-location`) carry what JSON-LD leaves out:
                       per-card ranking, ad flags, review counts, shop sales
                       and tenure.

  data-appears-*       analytics attributes whose `data-appears-event-data`
                       payload is JSON. This is where the AI review-sentiment
                       tags and the per-listing/per-shop rating counts live,
                       and it is the only place they appear at all.

Two absences are load-bearing and are surfaced as nulls rather than guessed:

* Bestseller / Star Seller badges are NOT in grid HTML. The listing-card
  render config in the page says `badges_disabled: true` and the experiment
  `quality_signals.bestseller_logic_desktop` is `off`, so the badge markup is
  never emitted server side, on any locale or exit country tried. The parser
  reads the badge when Etsy does emit one (listing pages do, e.g. Etsy's Pick)
  and reports null otherwise -- see `bestsellerOnly` in the README.

* Seller SEO tags are gone from listing pages: there is not a single
  `/market/<tag>` link left on one. What remains, and is extracted instead, is
  the taxonomy path, the structured item attributes, and the AI review tags.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from selectolax.parser import HTMLParser, Node

from .constants import SHOP_LOCALE_DEFAULT, SITE_ROOT

log = logging.getLogger("etsy.parsers")

LISTING_URL_RE = re.compile(r"/listing/(\d+)/([a-z0-9\-]+)", re.I)
SHOP_URL_RE = re.compile(r"/shop/([A-Za-z0-9_\-]+)")
LOCALE_PREFIX_RE = re.compile(r"^https?://www\.etsy\.com/(?:([a-z]{2}(?:-[a-z]{2})?)/)?", re.I)
INT_RE = re.compile(r"[\d.,]+")


# -- small helpers ---------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    t = node.text(strip=True)
    return t or None


def _clean_text(node: Node | None) -> str | None:
    """Visible text only, with a space between nodes.

    Etsy's Collage components are declarative shadow DOM: every icon carries a
    `<template>` holding a `<style>` block and an inline SVG. selectolax walks
    into those, so reading an element's text without removing them first
    returns CSS instead of copy. Decomposing on a *copy* of the node keeps the
    caller's tree intact for the other fields.
    """
    if node is None:
        return None
    clone = HTMLParser(node.html or "")
    for junk in clone.css("template, style, script, svg, noscript"):
        junk.decompose()
    t = re.sub(r"\s+", " ", clone.text(separator=" ", strip=True) or "").strip()
    return t or None


def _attr(node: Node | None, name: str) -> str | None:
    if node is None:
        return None
    v = node.attributes.get(name)
    return v.strip() if isinstance(v, str) and v.strip() else None


def _num(raw: Any) -> float | None:
    """Parse a number that may arrive as JSON or as localised display text.

    JSON-LD hands back real ints and floats (`reviewCount`, `eligibleQuantity`)
    while the markup hands back strings, and both feed the same fields, so
    this accepts either.

    Etsy localises thousands separators, so "14,387,687" (en), "14.387.687"
    (de) and "1 234" (fr) all have to land on the same value. The rule that
    works across all of them: strip spaces, then treat the last separator as a
    decimal point only when it is followed by exactly one or two digits and
    there is no other separator of that kind later in the string.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    raw = str(raw)
    m = INT_RE.search(raw.replace(" ", "").replace(" ", "").replace(" ", ""))
    if not m:
        return None
    s = m.group(0)
    if "," in s and "." in s:
        # Whichever separator comes last is the decimal one.
        dec = "," if s.rindex(",") > s.rindex(".") else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    else:
        for sep in (",", "."):
            if sep in s:
                tail = s.rsplit(sep, 1)[1]
                if len(tail) in (1, 2) and s.count(sep) == 1:
                    s = s.replace(sep, ".")
                else:
                    s = s.replace(sep, "")
    try:
        return float(s)
    except ValueError:
        return None


def _int(raw: Any) -> int | None:
    v = _num(raw)
    return int(v) if v is not None else None


def _abbrev_to_int(raw: str | None) -> int | None:
    """Turn Etsy's shop-header shorthand ("59.5k", "1.2M") into a number."""
    if not raw:
        return None
    m = re.search(r"([\d.,]+)\s*([kKmM]?)", raw)
    if not m:
        return None
    base = _num(m.group(1))
    if base is None:
        return None
    mult = {"k": 1_000, "m": 1_000_000}.get(m.group(2).lower(), 1)
    return int(base * mult)


def _unescape(s: str | None) -> str | None:
    return html_mod.unescape(s) if s else s


def listing_id_from_url(url: str) -> str | None:
    m = LISTING_URL_RE.search(url or "")
    return m.group(1) if m else None


def shop_name_from_url(url: str) -> str | None:
    m = SHOP_URL_RE.search(url or "")
    return m.group(1) if m else None


def absolutise(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.etsy.com" + href
    return href


def shop_url_for(shop_name: str | None) -> str | None:
    """A shop URL that Etsy will actually serve.

    Always locale-prefixed: the bare `/shop/<name>` path is answered with the
    DataDome interstitial from every address and fingerprint tried, while the
    prefixed form is served. Emitting the bare form in a record would hand the
    user a link that only works in a browser with a cleared cookie.
    """
    if not shop_name:
        return None
    return f"{SITE_ROOT}/{SHOP_LOCALE_DEFAULT}/shop/{shop_name}"


def strip_tracking(url: str | None) -> str | None:
    """Drop Etsy's click-tracking query string.

    The grid emits hrefs carrying `click_key`, `click_sum`, `ga_*` and `ref`.
    They are per-impression and would make every run's URLs differ, defeating
    de-duplication downstream. The path itself -- id plus exact slug -- is the
    part that has to survive, because a wrong slug is what DataDome blocks.
    """
    if not url:
        return None
    return url.split("?", 1)[0]


# -- JSON-LD ---------------------------------------------------------------

_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)


def json_ld_blocks(html: str) -> list[Any]:
    out: list[Any] = []
    for m in _LD_RE.finditer(html):
        raw = m.group(1).strip()
        try:
            out.append(json.loads(raw))
        except Exception:  # noqa: BLE001 - one malformed block must not lose the rest
            continue
    return out


def _ld_of_type(blocks: Iterable[Any], wanted: str) -> dict[str, Any] | None:
    for b in blocks:
        items = b if isinstance(b, list) else [b]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == wanted:
                return it
    return None


# -- analytics payloads ----------------------------------------------------


def appears_data(html: str, component: str) -> dict[str, Any] | None:
    """Read the JSON payload of a `data-appears-component-name` element.

    The attribute order is fixed in Etsy's template (name then event-data), so
    a narrow regex is both correct and far cheaper than walking the tree of a
    600 KB document for one node.
    """
    m = re.search(
        r'data-appears-component-name="' + re.escape(component) + r'"\s+'
        r"data-appears-event-data='([^']*)'",
        html,
    )
    if not m:
        return None
    try:
        return json.loads(html_mod.unescape(m.group(1)))
    except Exception:  # noqa: BLE001
        return None


# -- listing cards (category grids and shop catalogues) --------------------


def parse_listing_cards(html: str) -> list[dict[str, Any]]:
    """Extract every product card from a grid page.

    One function serves category grids and shop catalogue pages because Etsy
    renders the identical `v2-listing-card` component on both.
    """
    tree = HTMLParser(html)
    cards: list[dict[str, Any]] = []

    for idx, card in enumerate(tree.css("div.v2-listing-card[data-listing-id]")):
        listing_id = _attr(card, "data-listing-id")
        if not listing_id:
            continue
        link = card.css_first("a.listing-link") or card.css_first("a[href*='/listing/']")
        url = strip_tracking(absolutise(_attr(link, "href")))

        seller_node = card.css_first("p[data-seller-name-container] span[aria-hidden='true']")
        seller_raw = _text(seller_node)
        # An advertised card puts the literal string "Ad by Etsy seller" where
        # an organic one puts the shop name, so the ad flag and the shop name
        # come from the same node and can never disagree.
        is_ad = bool(seller_raw and seller_raw.lower().startswith("ad by"))
        shop_name = None if is_ad else seller_raw

        # The stars and the count beside them on a grid card describe the
        # SHOP, not this listing: a card for listing 4306368113 reports 4.72
        # and 9,023, while the listing's own page reports 4.7 and 2,282 and
        # its shop reports exactly 9,023. Every card from one shop in a grid
        # carries the same pair, which is the same thing said another way.
        # They are named for what they are so nobody joins on the wrong one.
        rating_input = card.css_first("input[name='rating']")
        shop_review_count = None
        for cand in card.css("span"):
            t = cand.text(strip=True)
            # "(30% off)" sits in an identical-looking span, so the content
            # has to be a bare number or the discount gets read as a count.
            if re.fullmatch(r"\(\s*[\d.,]+\s*\)", t or ""):
                shop_review_count = _int(t)
                break

        price_block = card.css_first("div.n-listing-card__price")
        price = original_price = currency = discount = None
        if price_block is not None:
            values = [_text(n) for n in price_block.css("span.currency-value")]
            symbols = [_text(n) for n in price_block.css("span.currency-symbol")]
            currency = symbols[0] if symbols else None
            if values:
                price = _num(values[0])
            if len(values) > 1:
                original_price = _num(values[1])
            for sr in price_block.css("span.wt-screen-reader-only"):
                t = sr.text(strip=True)
                if "%" in t:
                    discount = t
            disc = [n for n in price_block.css("span") if "% off" in (n.text(strip=True) or "")]
            if disc:
                discount = disc[-1].text(strip=True).strip("()")

        img = card.css_first("img[data-listing-card-listing-image]") or card.css_first("img")
        badges = [
            b for b in (_text(n) for n in card.css("span.wt-badge")) if b and b != "0"
        ]

        cards.append(
            {
                "listingId": listing_id,
                "title": _unescape(_text(card.css_first("h3"))),
                "url": url,
                "shopId": _attr(card, "data-shop-id"),
                "shopName": shop_name,
                "shopUrl": shop_url_for(shop_name),
                "price": price,
                "originalPrice": original_price,
                "currencySymbol": currency,
                "discount": discount,
                "shopRating": _num(_attr(rating_input, "value")),
                "shopReviewCount": shop_review_count,
                "imageUrl": _attr(img, "src"),
                "imageAlt": _unescape(_attr(img, "alt")),
                "isAd": is_ad,
                "freeShipping": any("free shipping" in b.lower() for b in badges),
                "badges": badges or None,
                # Etsy does not render Bestseller/Star Seller in grid HTML at
                # all (badges_disabled). Null means "not stated", not "no".
                "isBestseller": True if any("bestseller" in b.lower() for b in badges) else None,
                "isStarSeller": True if any("star seller" in b.lower() for b in badges) else None,
                "positionOnPage": idx + 1,
            }
        )
    return cards


def parse_grid(html: str) -> list[dict[str, Any]]:
    """Every product on a grid page, with both layers merged.

    Shop pages carry an ItemList JSON-LD alongside the cards, and the two know
    different things: the JSON-LD has the ISO currency code and the list
    price, the markup has the ad flag, the shop-level rating and the position
    on the page. Category grids have no ItemList at all. Merging on listing ID
    means one record shape regardless of which surface produced it, without
    inventing a currency code on the surface that does not publish one.
    """
    cards = parse_listing_cards(html)
    ld = {item["listingId"]: item for item in parse_shop_catalogue(html) if item.get("listingId")}
    if not ld:
        return cards
    if not cards:
        return list(ld.values())
    for card in cards:
        extra = ld.pop(card.get("listingId"), None)
        if not extra:
            continue
        for key, value in extra.items():
            if value is not None and card.get(key) is None:
                card[key] = value
    # Anything the JSON-LD listed but the markup did not render (Etsy splits
    # some shop grids across desktop/mobile blocks) is still a real product.
    merged = cards + list(ld.values())

    # One page is priced in one currency, so the ISO code from any JSON-LD
    # entry applies to the cards the JSON-LD did not cover -- Etsy's own
    # "Featured items" strip, which renders only the symbol. Filling it in is
    # what makes a shop's whole catalogue comparable in one column.
    page_currency = next(
        (item.get("currency") for item in merged if item.get("currency")), None
    )
    for item in merged:
        if page_currency and not item.get("currency"):
            item["currency"] = page_currency
        # A shop catalogue page names the seller only in its JSON-LD, so the
        # link has to be derived after the two layers have been put together.
        if not item.get("shopUrl"):
            item["shopUrl"] = shop_url_for(item.get("shopName"))
    return merged


def has_next_page(html: str, current_page: int) -> bool:
    """Whether Etsy itself offers a page after this one.

    Read from the pagination nav rather than inferred from card count: an
    empty grid is not a reliable end marker on this site (see
    EMPTY_PAGE_TOLERANCE).
    """
    tree = HTMLParser(html)
    for a in tree.css("nav.search-pagination a[data-page]"):
        page = _int(_attr(a, "data-page"))
        if page and page > current_page:
            return True
    return False


# -- shop keyword search ---------------------------------------------------


def parse_shop_search(html: str) -> list[dict[str, Any]]:
    """Extract shop cards from /search/shops?q=<keyword>.

    This is the only keyword entry point Etsy's robots.txt allows (it carries
    an explicit `Allow: /search/shops` per locale), and it genuinely filters:
    distinct shops per keyword, and zero results for a nonsense query.
    """
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, link in enumerate(tree.css("a.wt-card__link[href*='/shop/']")):
        href = absolutise(_attr(link, "href"))
        name = shop_name_from_url(href or "")
        if not name or name in seen:
            continue
        seen.add(name)

        paragraphs = [p.text(strip=True) for p in link.css("p") if p.text(strip=True)]
        title = paragraphs[0] if paragraphs else name
        tagline = None
        item_count = None
        for p in paragraphs[1:]:
            if re.match(r"^[\d.,]+\s+items?$", p, re.I):
                item_count = _int(p)
            elif tagline is None:
                tagline = p

        card = link.parent.parent if link.parent is not None else None
        previews = []
        if card is not None:
            previews = [
                src
                for src in (_attr(i, "src") for i in card.css("img"))
                if src and "/il/" in src
            ]

        out.append(
            {
                "shopName": name,
                "shopTitle": _unescape(title),
                "tagline": _unescape(tagline),
                "itemCount": item_count,
                "shopUrl": strip_tracking(href),
                "avatarUrl": _attr(link.css_first("img"), "src"),
                "previewImages": previews or None,
                "positionOnPage": idx + 1,
            }
        )
    return out


def _star_seller(tree: HTMLParser) -> bool | None:
    """Whether the shop carries Etsy's Star Seller badge.

    Returns None rather than False when nothing is found, because the phrase
    also appears in every page's JS translation bundle and in module preload
    URLs -- those are not evidence either way, so only a rendered badge or
    heading counts, and its absence is reported as "not stated".
    """
    for node in tree.css("span.wt-badge, h2, h3, p, div[data-star-seller]"):
        if "star seller" in (node.text(strip=True) or "").lower()[:40]:
            return True
    return None


# -- shop profile ----------------------------------------------------------


def parse_shop_profile(html: str, url: str) -> dict[str, Any]:
    blocks = json_ld_blocks(html)
    org = _ld_of_type(blocks, "Organization") or {}
    tree = HTMLParser(html)

    highlights: dict[str, str] = {}
    for h in tree.css("div.highlight[data-highlight]"):
        key = _attr(h, "data-highlight")
        val = _text(h.css_first("div.highlight__primary-content"))
        if key and val:
            highlights[key] = val

    # The header states sales exactly ("59,504") next to the abbreviated
    # highlight ("59.5k"); prefer the exact one and keep the other as a
    # fallback for shops that only render the compact header.
    sales_exact = None
    since_year = None
    for div in tree.css("div"):
        t = div.text(strip=True)
        if t.startswith("Sales") and len(t) < 40:
            sales_exact = _int(t[5:])
        elif t.startswith("On Etsy since") and len(t) < 40:
            since_year = _int(t[13:])
        if sales_exact is not None and since_year is not None:
            break

    faq = _ld_of_type(blocks, "FAQPage") or {}
    faqs = [
        {
            "question": _unescape(q.get("name")),
            "answer": _unescape((q.get("acceptedAnswer") or {}).get("text")),
        }
        for q in (faq.get("mainEntity") or [])
        if isinstance(q, dict)
    ]

    employees = [
        {"name": e.get("name"), "role": e.get("jobTitle")}
        for e in (org.get("employee") or [])
        if isinstance(e, dict)
    ]

    name = org.get("name") or _text(tree.css_first("h1.shop-name")) or shop_name_from_url(url)

    # Etsy publishes two different ratings and they legitimately disagree: the
    # Organization JSON-LD carries the all-time average, while the shop header
    # shows a recency-weighted one ("a rating's value decreasing by half each
    # year"). Both are kept rather than picking a winner.
    agg = org.get("aggregateRating") or {}
    rating_all_time = _num(agg.get("ratingValue"))
    rating_recent = _num(_attr(tree.css_first("div[data-review-ratings-count][data-rating]"), "data-rating"))

    # The numeric shop id is what tells this shop's own listings apart from
    # the recommendation carousels Etsy mixes into some shop layouts, which
    # carry a different data-shop-id. It is in the page's JS config rather
    # than anywhere visible.
    shop_id_match = re.search(r'"shop_?[Ii]d":(\d+)', html)

    return {
        "shopName": name,
        "shopId": shop_id_match.group(1) if shop_id_match else None,
        "shopUrl": strip_tracking(url),
        "title": _unescape(org.get("slogan")) or _unescape(_text(tree.css_first("h1.shop-name"))),
        "description": _unescape(org.get("description")),
        "location": org.get("location") or _text(tree.css_first("p.sb-shop-location")),
        "logoUrl": org.get("logo"),
        "bannerUrl": org.get("image"),
        "totalSales": sales_exact if sales_exact is not None else _abbrev_to_int(highlights.get("sales")),
        "onEtsySince": since_year,
        "rating": rating_all_time if rating_all_time is not None else rating_recent,
        "ratingAllTime": rating_all_time,
        "ratingRecencyWeighted": rating_recent,
        "reviewCount": _int(agg.get("reviewCount")),
        "announcement": _unescape(_clean_text(tree.css_first("#announcement"))),
        "members": employees or None,
        "faqs": faqs or None,
        "isStarSeller": _star_seller(tree),
    }


def parse_shop_catalogue(html: str) -> list[dict[str, Any]]:
    """The shop's visible catalogue, from its ItemList JSON-LD.

    Preferred over the card markup here because the ItemList carries the
    locale-correct currency code (GBP, EUR) rather than the rendered symbol,
    and the list price alongside the sale price.
    """
    item_list = _ld_of_type(json_ld_blocks(html), "ItemList") or {}
    out: list[dict[str, Any]] = []
    for entry in item_list.get("itemListElement") or []:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item") or {}
        if not isinstance(item, dict):
            continue
        offers = item.get("offers") or {}
        spec = offers.get("priceSpecification") or {}
        if isinstance(spec, list):
            spec = spec[0] if spec else {}
        url = item.get("url")
        out.append(
            {
                "listingId": listing_id_from_url(url or ""),
                "title": _unescape(item.get("name")),
                "url": strip_tracking(url),
                "imageUrl": item.get("image"),
                "shopName": (item.get("brand") or {}).get("name"),
                "price": _num(offers.get("price")),
                "originalPrice": _num(spec.get("price")) if isinstance(spec, dict) else None,
                "currency": offers.get("priceCurrency"),
                "availability": (offers.get("availability") or "").rsplit("/", 1)[-1] or None,
                "positionOnPage": entry.get("position"),
            }
        )
    return out


# -- product detail --------------------------------------------------------


def parse_product_detail(html: str, url: str) -> dict[str, Any]:
    blocks = json_ld_blocks(html)
    product = _ld_of_type(blocks, "Product") or {}
    crumbs = _ld_of_type(blocks, "BreadcrumbList") or {}
    faq = _ld_of_type(blocks, "FAQPage") or {}
    tree = HTMLParser(html)

    offers = product.get("offers") or {}
    specs = offers.get("priceSpecification") or []
    if isinstance(specs, dict):
        specs = [specs]
    sale_spec = next(
        (s for s in specs if isinstance(s, dict) and "Strikethrough" not in str(s.get("priceType"))),
        {},
    )
    strike_spec = next(
        (s for s in specs if isinstance(s, dict) and "Strikethrough" in str(s.get("priceType"))),
        {},
    )

    images = []
    for img in product.get("image") or []:
        if isinstance(img, dict):
            images.append(
                {
                    "url": img.get("contentURL"),
                    "thumbnail": img.get("thumbnail"),
                    "alt": _unescape(img.get("description")),
                }
            )
        elif isinstance(img, str):
            images.append({"url": img, "thumbnail": None, "alt": None})

    breadcrumbs = [
        {"name": c.get("name"), "url": strip_tracking(c.get("item"))}
        for c in (crumbs.get("itemListElement") or [])
        if isinstance(c, dict)
    ]

    # Variation option groups. Etsy renders one <select> per variation with a
    # label; the option list is the buyer's actual choice set.
    variations = []
    for sel in tree.css("select[id^='variation-selector']"):
        label = None
        sid = _attr(sel, "id")
        if sid:
            lab = tree.css_first(f"label[for='{sid}']")
            label = _text(lab)
        options = [
            _unescape(_text(o))
            for o in sel.css("option")
            if _text(o) and not _attr(o, "disabled")
        ]
        if options:
            variations.append({"name": label, "options": options})

    highlights = [
        h for h in (
            _unescape(_clean_text(li))
            for li in tree.css("ul[data-selector='product-details-highlights'] li")
        )
        if h
    ]

    # "Only N left" / "N people have this in their cart" urgency copy. Etsy
    # moves this between components, so match on the sentence, not the node.
    body_text = tree.body.text(separator=" ", strip=True) if tree.body else ""
    low_stock = None
    m = re.search(r"Only\s+(\d+)\s+left", body_text, re.I)
    if m:
        low_stock = _int(m.group(1))
    in_carts = None
    m = re.search(r"(\d+)\s+people have this in their (?:cart|basket)", body_text, re.I)
    if m:
        in_carts = _int(m.group(1))

    tenure = appears_data(html, "lp_seller_cred_tenure") or {}
    reviews_meta = appears_data(html, "listing_page_reviews") or {}
    feature_tags = appears_data(html, "reviews_feature_tags") or {}

    sales_text = None
    for div in tree.css("div.wt-text-title"):
        t = div.text(strip=True)
        if t and re.match(r"^[\d.,]+[kKmM]?\s+sales$", t):
            sales_text = t
            break

    agg = product.get("aggregateRating") or {}
    shop_name = (product.get("brand") or {}).get("name")
    badge_node = tree.css_first("div[data-appears-component-name='web_listing_badge'] button[aria-describedby]")
    badge = _attr(badge_node, "aria-describedby")

    return {
        "listingId": product.get("sku") or listing_id_from_url(url),
        "title": _unescape(product.get("name")),
        "url": strip_tracking(product.get("url") or url),
        "description": _unescape(product.get("description")),
        "shopName": shop_name,
        "shopUrl": shop_url_for(shop_name),
        "shopLogoUrl": product.get("logo"),
        "shopTotalSales": _abbrev_to_int(sales_text),
        "shopTenure": tenure.get("tenure"),
        "shopReviewCount": reviews_meta.get("shop_rating_count"),
        "categoryPath": product.get("category"),
        "breadcrumbs": breadcrumbs or None,
        "price": _num(offers.get("price")),
        "priceMin": _num(sale_spec.get("minPrice")),
        "priceMax": _num(sale_spec.get("maxPrice")),
        "originalPrice": _num(strike_spec.get("price")),
        "currency": offers.get("priceCurrency"),
        "availability": (offers.get("availability") or "").rsplit("/", 1)[-1] or None,
        "quantityAvailable": offers.get("eligibleQuantity"),
        "lowStockRemaining": low_stock,
        "peopleWithItemInCart": in_carts,
        "shipsFrom": ((offers.get("shippingDetails") or {}).get("shippingOrigin") or {}).get("addressCountry"),
        "rating": _num(agg.get("ratingValue")),
        "reviewCount": agg.get("reviewCount") or reviews_meta.get("listing_rating_count"),
        "images": images or None,
        "variations": variations or None,
        "highlights": highlights or None,
        "reviewFeatureTags": feature_tags.get("tags") or None,
        "reviewFeatureTagCounts": (
            {
                "positive": feature_tags.get("num_positive_tags"),
                "negative": feature_tags.get("num_negative_tags"),
            }
            if feature_tags
            else None
        ),
        "shopFaqs": [
            {
                "question": _unescape(q.get("name")),
                "answer": _unescape((q.get("acceptedAnswer") or {}).get("text")),
            }
            for q in (faq.get("mainEntity") or [])
            if isinstance(q, dict)
        ]
        or None,
        "listingBadge": badge,
        # Etsy stopped rendering seller SEO tags on listing pages; the fields
        # below are what is left of the keyword surface.
        "sellerTags": None,
    }


# -- reviews ---------------------------------------------------------------

_DATE_SUFFIX_RE = re.compile(r"\bon\s+(.+)$", re.I)


def _review_photos(node: Node) -> list[str]:
    """Buyer-uploaded photos.

    They are served from the `iap/` path on Etsy's image CDN, which the
    listing's own photos (`il/`) and the avatars (`isla/`) never use, so the
    path segment is a sound discriminator.
    """
    return [
        src
        for src in (_attr(i, "src") for i in node.css("img"))
        if src and "/iap/" in src
    ]


def parse_reviews(html: str, *, source_url: str) -> list[dict[str, Any]]:
    """Reviews from either surface.

    The shop reviews page renders `li[data-review-region]` with an attribution
    line and the purchased listing; the listing page renders
    `div.review-card[data-review-region]` for the handful it shows inline.
    Both are handled here because the fields are the same and callers should
    not have to care which page a review came from.
    """
    tree = HTMLParser(html)
    nodes = tree.css("li[data-review-region]") or tree.css("div.review-card[data-review-region]")
    if not nodes:
        # Not every listing page renders its reviews. Some variants ship the
        # reviews component with an empty body and fetch the contents from
        # /api/, which robots.txt disallows -- but the Product JSON-LD on the
        # same page often still carries the first few. It is a thinner record
        # (no review id, no photos, no purchased item) and is only used when
        # the markup has nothing, so a page that renders reviews is never
        # downgraded to it.
        return _reviews_from_json_ld(html, source_url=source_url)
    out: list[dict[str, Any]] = []

    for node in nodes:
        review_id = _attr(node, "data-review-region")
        rating = _int(_attr(node.css_first("input[name='rating']"), "value"))

        author = author_url = date_text = None
        attribution = node.css_first("p.shop2-review-attribution")
        if attribution is not None:
            link = attribution.css_first("a")
            author_url = strip_tracking(absolutise(_attr(link, "href")))
            line = _clean_text(attribution) or ""
            m = _DATE_SUFFIX_RE.search(line)
            date_text = m.group(1).strip() if m else None
            # Some buyers have no public profile, so the name is plain text
            # rather than a link. Taking whatever precedes " on <date>" reads
            # both shapes, and falls back to the link when the line is only a
            # date (a fully anonymous review).
            author = _text(link) or (line[: m.start()].strip(" -·|") or None if m else None)
        else:
            link = node.css_first("a[data-review-username]")
            author = _text(link)
            author_url = strip_tracking(absolutise(_attr(link, "href")))
            holder = link.parent if link is not None else None
            if holder is not None:
                # The date follows the name inside the same <p>; removing the
                # name leaves it on its own.
                rest = holder.text(strip=True)
                if author and rest.startswith(author):
                    date_text = rest[len(author):].strip(" ·|") or None
                else:
                    date_text = rest or None

        body = None
        for p in node.css("p.prose, p[id^='review-preview-t'], div.wt-text-body p"):
            t = p.text(strip=True)
            if t and len(t) > (len(body or "")):
                body = t

        purchased = node.css_first("div[data-region='listing'] a[href*='/listing/']")
        purchased_url = strip_tracking(absolutise(_attr(purchased, "href")))

        response_node = node.css_first("div[data-region='response']")
        response = _text(response_node)

        out.append(
            {
                "reviewId": review_id,
                "rating": rating,
                "text": _unescape(body),
                "date": date_text,
                "buyerName": _unescape(author),
                "buyerProfileUrl": author_url,
                "photos": _review_photos(node) or None,
                "sellerResponse": _unescape(response),
                "purchasedListingId": listing_id_from_url(purchased_url or ""),
                "purchasedListingUrl": purchased_url,
                "purchasedListingTitle": _unescape(_attr(purchased, "aria-label")),
                "sourceUrl": strip_tracking(source_url),
            }
        )
    return out


def _reviews_from_json_ld(html: str, *, source_url: str) -> list[dict[str, Any]]:
    product = _ld_of_type(json_ld_blocks(html), "Product") or {}
    listing_id = product.get("sku") or listing_id_from_url(source_url)
    out: list[dict[str, Any]] = []
    for entry in product.get("review") or []:
        if not isinstance(entry, dict):
            continue
        out.append(
            {
                "reviewId": None,
                "rating": _int((entry.get("reviewRating") or {}).get("ratingValue")),
                "text": _unescape(entry.get("reviewBody")),
                "date": entry.get("datePublished"),
                "buyerName": _unescape((entry.get("author") or {}).get("name")),
                "buyerProfileUrl": None,
                "photos": None,
                "sellerResponse": None,
                "purchasedListingId": listing_id,
                "purchasedListingUrl": strip_tracking(source_url),
                "purchasedListingTitle": _unescape(product.get("name")),
                "sourceUrl": strip_tracking(source_url),
                "_source": "json-ld",
            }
        )
    return out


def parse_review_sentiment(html: str) -> dict[str, Any] | None:
    """Etsy's AI-summarised review tags, with their sentiment split.

    This is the only aggregated sentiment Etsy publishes, and it exists only
    in an analytics payload -- there is no equivalent in the visible copy or
    in JSON-LD.
    """
    tags = appears_data(html, "reviews_feature_tags")
    if not tags:
        return None
    tree = HTMLParser(html)
    typed = [
        {"tag": _attr(n, "data-tag"), "type": _attr(n, "data-tag-type")}
        for n in tree.css("span[data-tag][data-tag-type]")
    ]
    return {
        "tags": tags.get("tags") or None,
        "taggedAspects": typed or None,
        "positiveTagCount": tags.get("num_positive_tags"),
        "negativeTagCount": tags.get("num_negative_tags"),
    }


# -- record envelope -------------------------------------------------------


def record(
    item_type: str,
    item_id: str | None,
    data: dict[str, Any],
    *,
    source_url: str,
    mode: str,
    keyword: str | None = None,
    rank: int | None = None,
    page: int | None = None,
    parent_id: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    return {
        "item_type": item_type,
        "id": item_id,
        "data": data,
        "metadata": {
            "scrapedAt": now_iso(),
            "sourceUrl": strip_tracking(source_url),
            "mode": mode,
            "keyword": keyword,
            "rank": rank,
            "page": page,
            "parentId": parent_id,
            "locale": locale,
        },
    }


def error_record(
    input_ref: str, error: str, detail: str, *, mode: str = "", item_type: str = "error"
) -> dict[str, Any]:
    return {
        "item_type": item_type,
        "id": None,
        "data": {"_error": error, "_errorDetail": detail, "_input": input_ref},
        "metadata": {
            "scrapedAt": now_iso(),
            "sourceUrl": input_ref if input_ref.startswith("http") else None,
            "mode": mode,
            "keyword": None,
            "rank": None,
            "page": None,
            "parentId": None,
            "locale": None,
        },
    }
