"""Parsers for the two Google Hotels surfaces.

Google's CSS class names are minified and change on every deploy, so nothing
here selects on them. The anchors used instead are semantic and have survived
years of Google redesigns:

* ``a[href^="/travel/hotels/entity/"]`` with an ``aria-label`` -- a hotel card.
* ``a[href*="/travel/lodging/clk"]`` with ``data-is-organic`` -- one organic
  OTA quote, with the partner id on an ancestor ``div[data-partner-id]``.
* ``a[href*="/aclk?"]`` -- a paid placement for a *different* hotel.
* ``aria-label="<n> out of 5 stars from <m> reviews"`` -- rating and volume.

Everything else is read out of the card's own visible text with anchored
patterns, scoped to one card's subtree rather than the whole page -- which is
what keeps the label-contamination trap from the BCPEA Actor (a filter caption
matching before the content did) from reappearing here.
"""

import re
from urllib.parse import parse_qs, urlparse

from selectolax.parser import HTMLParser

from src.constants import SECONDARY_LABEL_PREFIXES

# "IDR 1,350,000" / "$189" / "EUR 240" -- a currency code then an amount, or a symbol.
MONEY = re.compile(
    r"(?:(?P<code>[A-Z]{2,3})\s*|(?P<sym>[$€£¥₹]))\s?(?P<amount>\d[\d.,]*)"
)
# Google appends a verdict on the entity page ("... reviews. Excellent.") but
# not on search cards, so this is a search, never a full match.
RATING_ARIA = re.compile(r"([\d.]+) out of 5 stars from ([\d,]+) reviews")
PHONE = re.compile(r"^\+[\d\s()\-]{7,}$")
STAR_CLASS = re.compile(r"(\d)-star hotel")
DEAL_PCT = re.compile(r"(\d+)% (less|more) than usual")
# "Sep 28 - 29" / "Nov 6 - 8" -- Google renders an en dash, hence the class.
DATE_WINDOW = re.compile(
    r"([A-Z][a-z]{2} \d{1,2}(?:\s*[–—-]\s*(?:[A-Z][a-z]{2} )?\d{1,2})?)"
)
REVIEW_COUNT = re.compile(r"\(([\d.]+[KM]?)\)")
NIGHTS = re.compile(r"(\d+) nights? with taxes \+ fees")

PROPERTY_TYPES = (
    "House",
    "Apartment",
    "Villa",
    "Hostel",
    "Hotel",
    "Resort",
    "Guest house",
    "Bungalow",
    "Cottage",
)

KNOWN_FEATURES = ("Free cancellation", "Spa", "Pool", "Pools", "Hot tub", "Breakfast", "Kid-friendly")


def _text(node, sep: str = "|") -> str:
    return re.sub(r"\s+", " ", node.text(separator=sep)) if node is not None else ""


def _money(text: str) -> tuple[str | None, str | None, float | None]:
    """First price in ``text`` as ``(raw, currency, numeric)``."""
    m = MONEY.search(text or "")
    if not m:
        return None, None, None
    raw = m.group(0).strip()
    currency = m.group("code") or m.group("sym")
    digits = m.group("amount").replace(",", "")
    # Locales that use "." as a thousands separator would otherwise turn
    # 1.350.000 into 1.35, so a dot only counts as decimal when it is the only
    # one and leaves fewer than three digits behind it.
    if digits.count(".") > 1 or ("." in digits and len(digits.split(".")[-1]) == 3):
        digits = digits.replace(".", "")
    try:
        numeric = float(digits)
    except ValueError:
        numeric = None
    return raw, currency, numeric


def _entity_id(href: str) -> str | None:
    if "/travel/hotels/entity/" not in href:
        return None
    return href.split("/travel/hotels/entity/")[1].split("?")[0].split("/")[0]


def _ancestor_attr(node, attr: str, depth: int = 10) -> str | None:
    cur = node
    for _ in range(depth):
        cur = cur.parent
        if cur is None:
            return None
        value = cur.attributes.get(attr)
        if value:
            return value
    return None


def _card_root(node, depth: int = 7):
    """Climb from a card's title link to the node holding the whole card.

    The card is the first ancestor whose text has several segments; the title
    link alone has none. Climbing by shape rather than by class name is what
    keeps this working after Google reshuffles its markup.
    """
    cur = node
    for _ in range(depth):
        cur = cur.parent
        if cur is None:
            break
        if _text(cur).count("|") >= 4:
            return cur
    return None


def _expand_count(text: str) -> int | None:
    """"2.9K" -> 2900. Google abbreviates review counts on cards."""
    try:
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(float(text))
    except ValueError:
        return None


def parse_search(html: str, query: str) -> list[dict]:
    """One record per hotel card on a ``/travel/search`` page."""
    tree = HTMLParser(html)
    out: dict[str, dict] = {}
    amenities_by_name = _amenity_index(tree)

    for link in tree.css('a[href^="/travel/hotels/entity/"]'):
        label = (link.attributes.get("aria-label") or "").strip()
        href = link.attributes.get("href") or ""
        entity_id = _entity_id(href)
        if not label or not entity_id or label.startswith(SECONDARY_LABEL_PREFIXES):
            continue
        if entity_id in out:
            continue

        card = _card_root(link)
        segments = [s.strip() for s in _text(card).split("|") if s.strip()]

        record = {
            "entityId": entity_id,
            "name": label,
            "hotelUrl": f"https://www.google.com/travel/hotels/entity/{entity_id}",
            "searchQuery": query,
        }
        record.update(_card_price(segments))
        record.update(_card_quality(card, segments))
        record["amenities"] = amenities_by_name.get(label, [])
        record["reviewThemes"] = _card_themes(segments)
        record["_source"] = "travel-search-ssr"
        out[entity_id] = record

    return list(out.values())


def _card_price(segments: list[str]) -> dict:
    joined = " ".join(segments)
    raw, currency, numeric = _money(joined)
    nights = NIGHTS.search(joined)
    window = DATE_WINDOW.search(joined)
    deal = DEAL_PCT.search(joined)
    return {
        "priceRaw": raw,
        "currency": currency,
        "price": numeric,
        "priceIsTotal": "total" in joined.lower(),
        "priceIncludesTaxes": "with taxes + fees" in joined,
        "nights": int(nights.group(1)) if nights else None,
        # The window Google actually priced. It is NOT a window the caller can
        # choose -- see the PAGINATION/date notes in constants.py.
        "stayWindow": window.group(1) if window else None,
        "dealFlag": (
            "GREAT PRICE"
            if "GREAT PRICE" in joined
            else (f"{deal.group(1)}% {deal.group(2)} than usual" if deal else None)
        ),
        "dealPercent": int(deal.group(1)) if deal else None,
    }


def _card_quality(card, segments: list[str]) -> dict:
    rating = None
    review_count = None
    if card is not None:
        for node in card.css("[aria-label]"):
            m = RATING_ARIA.search(node.attributes.get("aria-label") or "")
            if m:
                rating = float(m.group(1))
                review_count = int(m.group(2).replace(",", ""))
                break

    joined = " ".join(segments)
    if rating is None:
        # Cards for small properties print "4.8" and "(8)" without the aria
        # summary, so fall back to the visible pair.
        m = re.search(r"\b([1-5]\.\d)\b", joined)
        rating = float(m.group(1)) if m else None
        rc = REVIEW_COUNT.search(joined)
        if rc:
            review_count = _expand_count(rc.group(1))

    stars = STAR_CLASS.search(joined)
    return {
        "rating": rating,
        "reviewCount": review_count,
        "starClass": int(stars.group(1)) if stars else None,
        "propertyType": next((s for s in segments if s in PROPERTY_TYPES), None),
    }


AMENITY_PREFIX = "Amenities for"
# "Amenities for THE GENERAL KYOTO, a 4-star hotel.: Free Wi-Fi, Parking"
AMENITY_STAR_SUFFIX = re.compile(r",\s*(?:a|an)\s+\d-star hotel\.?$")


def _amenity_index(tree) -> dict[str, list[str]]:
    """Map hotel name -> amenity list for a whole search page.

    Google publishes the amenity list in **two different shapes** depending on
    the page variant: as an ``aria-label`` (seen on Bali results) and as the
    text of a ``span[role="document"]`` (seen on Kyoto results). Worse, the
    node sits *outside* the card's ancestor chain -- a search up 12 levels from
    the title link never reaches it -- so the list is indexed once per page by
    the hotel name it names, rather than looked for inside each card.
    """
    index: dict[str, list[str]] = {}

    def record(blob: str) -> None:
        if not blob.startswith(AMENITY_PREFIX) or ":" not in blob:
            return
        head, tail = blob.split(":", 1)
        name = AMENITY_STAR_SUFFIX.sub("", head[len(AMENITY_PREFIX) :].strip()).strip().rstrip(".")
        amenities = [a.strip() for a in tail.split(",") if a.strip()]
        if name and amenities:
            index[name] = amenities

    for node in tree.css("[aria-label]"):
        record((node.attributes.get("aria-label") or "").strip())
    for node in tree.css('span[role="document"]'):
        record(re.sub(r"\s+", " ", node.text() or "").strip())

    return index


def _card_themes(segments: list[str]) -> list[str]:
    """The "People often mention" block, split on Google's middle dots."""
    try:
        idx = segments.index("People often mention")
    except ValueError:
        return []
    themes: list[str] = []
    for seg in segments[idx + 1 : idx + 4]:
        if MONEY.search(seg) or seg.startswith("Amenities for"):
            break
        themes += [t.strip() for t in re.split(r"[·•]", seg) if t.strip()]
    return themes


class HollowEntityPage(Exception):
    """Google served its own error page under HTTP 200 for this entity id."""


# Google does not 404 an unknown entity id. It answers 200 with a full-size
# error page whose <h1> is this text, which a naive parser happily emits as a
# hotel named "Oops, something went wrong".
GOOGLE_ERROR_HEADINGS = (
    "oops, something went wrong",
    "something went wrong",
    "we couldn't find",
    "page not found",
)


def parse_entity(entity_id: str, html: str) -> dict:
    """Hotel detail plus every organic OTA quote on the prices page."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    name = h1.text().strip() if h1 is not None else None
    if not name:
        raise ValueError(
            f"no <h1> on the entity page for {entity_id} -- Google changed the page "
            f"shape or served a variant this parser has not seen"
        )
    if any(name.lower().startswith(p) for p in GOOGLE_ERROR_HEADINGS):
        raise HollowEntityPage(
            f"Google answered 200 with its own error page for entity id {entity_id!r} "
            f"(heading: {name!r}) -- the id does not exist or is no longer published"
        )

    rates = parse_rates(entity_id, html)
    prices = [r["price"] for r in rates if r.get("price") is not None]
    header = _entity_header(tree, name)

    record = {
        "entityId": entity_id,
        "name": name,
        "hotelUrl": f"https://www.google.com/travel/hotels/entity/{entity_id}",
        "address": header["address"],
        "phone": header["phone"],
        "rating": header["rating"],
        "reviewCount": header["reviewCount"],
        "starClass": header["starClass"],
        "stayWindow": header["stayWindow"],
        "currency": next((r["currency"] for r in rates if r.get("currency")), None),
        "rateCount": len(rates),
        "lowestRate": min(prices) if prices else None,
        "highestRate": max(prices) if prices else None,
        # The spread across OTAs for the same room-night is the number a rate
        # parity buyer is actually after, so it is computed here rather than
        # left for them to derive.
        "rateSpread": round(max(prices) - min(prices), 2) if len(prices) > 1 else None,
        "cheapestProvider": (
            min(
                (r for r in rates if r.get("price") is not None),
                key=lambda r: r["price"],
            )["provider"]
            if prices
            else None
        ),
        "rates": rates,
        "_source": "travel-entity-prices-ssr",
    }

    return record


def _entity_header(tree, name: str) -> dict:
    """Read the hotel's own facts out of the container holding its ``<h1>``.

    Scoping to that container matters more here than anywhere else in this
    Actor. An entity page also carries 18 paid placements for *other* hotels,
    a nearby-attractions block and a shopping-mall description, each with its
    own rating aria-label and its own postal address. A page-wide search for
    "the rating" or "the address" reliably returns a neighbour's: it produced
    4.4/18,459 for a hotel rated 4.7/64,684, and a jewellery boutique's
    marketing copy in place of the street address.
    """
    facts = {
        "address": None,
        "phone": None,
        "rating": None,
        "reviewCount": None,
        "starClass": None,
        "stayWindow": None,
    }
    h1 = tree.css_first("h1")
    if h1 is None:
        return facts

    # Climb until the container holds the header strip (name, star class,
    # address, phone) but stop before the whole page comes into scope.
    node = h1
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        segments = [s.strip() for s in _text(node).split("|") if s.strip() and s.strip() != "•"]
        if len(segments) < 3:
            continue

        joined = " ".join(segments)
        stars = STAR_CLASS.search(joined)
        if stars and facts["starClass"] is None:
            facts["starClass"] = int(stars.group(1))

        window = DATE_WINDOW.search(joined)
        if window and facts["stayWindow"] is None:
            facts["stayWindow"] = window.group(1)

        for seg in segments:
            if facts["phone"] is None and PHONE.match(seg):
                facts["phone"] = seg
            elif (
                facts["address"] is None
                and seg != name
                and 12 <= len(seg) <= 160
                and seg.count(",") >= 1
                and re.search(r"\d", seg)
                and not MONEY.search(seg)
                and not seg.endswith(".")
            ):
                facts["address"] = seg

        for aria_node in node.css("[aria-label]"):
            m = RATING_ARIA.search(aria_node.attributes.get("aria-label") or "")
            if m:
                facts["rating"] = float(m.group(1))
                facts["reviewCount"] = int(m.group(2).replace(",", ""))
                break

        if facts["rating"] is not None and facts["address"] is not None:
            break

    return facts


def parse_rates(entity_id: str, html: str) -> list[dict]:
    """One record per OTA quote for this hotel.

    Organic rows go through ``/travel/lodging/clk`` and carry the OTA's own
    deep link in the ``pcurl`` parameter, which is where the provider host
    comes from -- more reliable than the visible brand text, which is
    localised per exit country.
    """
    tree = HTMLParser(html)
    seen: set[tuple] = set()
    rates: list[dict] = []

    for link in tree.css('a[href*="/travel/lodging/clk"]'):
        href = (link.attributes.get("href") or "").replace("&amp;", "&")
        text = _text(link)
        segments = [s.strip() for s in text.split("|") if s.strip()]
        raw, currency, numeric = _money(text)
        pcurl = parse_qs(urlparse(href).query).get("pcurl", [None])[0]
        host = urlparse(pcurl).netloc if pcurl else None
        partner_id = _ancestor_attr(link, "data-partner-id")

        key = (partner_id, host, raw)
        if key in seen:
            continue
        seen.add(key)

        rates.append(
            {
                "entityId": entity_id,
                "provider": segments[0] if segments else None,
                "providerHost": host,
                "partnerId": partner_id,
                "isOrganic": link.attributes.get("data-is-organic") == "true",
                "priceRaw": raw,
                "currency": currency,
                "price": numeric,
                "rateType": next(
                    (s for s in segments if "per night" in s.lower() or "stay total" in s.lower()),
                    None,
                ),
                "includesTaxes": any("taxes + fees" in s for s in segments),
                "freeCancellation": any("Free cancellation" in s for s in segments),
                "bookingUrl": pcurl,
                "_source": "travel-entity-prices-ssr",
            }
        )
    return rates


def parse_sponsored(entity_id: str, html: str) -> list[dict]:
    """Paid placements on the entity page.

    These are quotes for **other** hotels, so they are never mixed into
    ``rates``: treating an ad for a competitor as this hotel's price is the
    single easiest way to corrupt a rate-parity dataset.
    """
    tree = HTMLParser(html)
    out: dict[str, dict] = {}

    for link in tree.css('a[href*="/aclk?"]'):
        text = _text(link)
        segments = [s.strip() for s in text.split("|") if s.strip() and s.strip() != "·"]
        if len(segments) < 3:
            continue
        name = segments[0]
        if MONEY.search(name):
            continue

        raw, currency, numeric = _money(text)
        provider = next((s for s in segments if s.startswith("Visit ")), None)
        stars = STAR_CLASS.search(text)
        rating = re.search(r"([\d.]+)/5", text)
        rc = REVIEW_COUNT.search(text)

        out.setdefault(
            f"{name}|{raw}",
            {
                "sourceEntityId": entity_id,
                "name": name,
                "priceRaw": raw,
                "currency": currency,
                "price": numeric,
                "provider": provider.replace("Visit ", "") if provider else None,
                "rating": float(rating.group(1)) if rating else None,
                "reviewCount": _expand_count(rc.group(1)) if rc else None,
                "starClass": int(stars.group(1)) if stars else None,
                "features": [s for s in segments[1:] if s in KNOWN_FEATURES],
                "placement": "sponsored",
                "_source": "travel-entity-prices-ssr",
            },
        )

    return list(out.values())


def extract_error(identifier: str, reason: str, detail: str) -> dict:
    return {
        "entityId": identifier,
        "error": reason,
        "errorDetail": detail,
        "_source": "error",
    }


def wrap_reference(
    url: str,
    available: bool,
    note: str,
    sample: dict | None = None,
    profile: str | None = None,
) -> dict:
    return {
        "probedUrl": url,
        "isAvailable": available,
        "note": note,
        "winningTlsProfile": profile,
        "sample": sample or {},
        "_source": "reference",
    }
