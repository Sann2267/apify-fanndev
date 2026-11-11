"""Portal HTML -> dataset records.

Both the list cards and the detail pages are built from the same primitive: a
``div.label__group`` holding ``div.label`` (the Bulgarian field name) and
``div.info`` (the value). One parser therefore serves both, and a field the
portal adds later still lands in the record -- unmapped labels are kept under
``fields`` instead of being dropped.

Bulgarian labels are translated into English field names because the buyer of
this dataset is not necessarily a Bulgarian speaker, but the original label and
value always ship inside ``fields`` so nothing is lost in translation.

Dates are the portal's ``DD.MM.YYYY``; they are converted to ISO so a dataset
sorts correctly. Prices arrive in **both EUR and BGN** on the same line since
the euro changeover, and both are kept -- converting one into the other would
invent precision the portal did not publish.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import BASE, FIELD_MAP, PRICE_LABEL

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_DATETIME_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})")
_PERIOD_RE = re.compile(r"от\s*(\d{2}\.\d{2}\.\d{4})\s*до\s*(\d{2}\.\d{2}\.\d{4})")  # "ot X do Y"
_PRICE_RE = re.compile(
    r"([\d\s .,]+)\s*(EUR|лв\.?)", re.I
)
_AREA_RE = re.compile(r"([\d\s .,]+)\s*(кв\.м|дка)", re.I)

# "Публикувано на 17 септември 2026 г. в 17:01 часа"
_BG_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3,
    "април": 4, "май": 5, "юни": 6, "юли": 7,
    "август": 8, "септември": 9,
    "октомври": 10, "ноември": 11, "декември": 12,
}
_PUBLISHED_RE = re.compile(
    r"Публикувано\s+на\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})[^\d]*(\d{2}):(\d{2})"
)


def published_to_iso(text):
    """The portal prints its publication date in Bulgarian words, not digits."""
    m = _PUBLISHED_RE.search(str(text or ""))
    if not m:
        return None
    month = _BG_MONTHS.get(m.group(2).lower())
    if not month:
        return None
    return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}T{m.group(4)}:{m.group(5)}:00"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(text) -> str | None:
    if text is None:
        return None
    value = re.sub(r"[\s ]+", " ", str(text)).strip()
    return value or None


def to_number(value):
    """'7 596.44' / '2 708.00' -> float, tolerating thin spaces and commas."""
    if value is None:
        return None
    text = re.sub(r"[\s ]", "", str(value)).replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def date_to_iso(value):
    m = _DATE_RE.search(str(value or ""))
    if not m:
        return None
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def datetime_to_iso(value):
    m = _DATETIME_RE.search(str(value or ""))
    if not m:
        return date_to_iso(value)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4)}:{m.group(5)}:00"


def _envelope(input_value: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": "S1-portal-html",
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def parse_label_groups(node) -> dict:
    """Every label/value pair inside a card or detail block, keyed by the
    portal's own Bulgarian label."""
    fields: dict[str, str] = {}
    for group in node.css("div.label__group"):
        label = group.css_first("div.label")
        info = group.css_first("div.info")
        if not label or not info:
            continue
        key = clean(label.text())
        value = clean(info.text())
        if key:
            # A label can repeat between the card block and the agent block;
            # the first occurrence is the property's own, so it wins.
            fields.setdefault(key, value)
    return fields


def _map_fields(fields: dict) -> dict:
    mapped = {}
    for label, value in fields.items():
        key = FIELD_MAP.get((label or "").strip().lower())
        if key:
            mapped[key] = value
    return mapped


def _prices(text: str) -> dict:
    """Starting price in both published currencies.

    The label appears twice on every page: once in the *filter* sidebar
    ("НАЧАЛНА ЦЕНА  Избери  до 10 000 лв ...") and once on the sale itself. A
    naive first-match scan reads the filter's dropdown bounds as the price --
    which is exactly what the first build did, reporting 10 000 BGN for every
    property. Windows containing the filter's "Избери" ("choose") are therefore
    skipped, and a window is only accepted once it yields a real amount.
    """
    out = {"startingPriceEur": None, "startingPriceBgn": None, "startingPriceRaw": None}
    lower = (text or "").lower()
    start = 0
    while True:
        i = lower.find(PRICE_LABEL, start)
        if i < 0:
            return out
        start = i + len(PRICE_LABEL)
        window = text[i: i + 120]
        if "Избери" in window:  # the filter dropdown, not a price
            continue
        eur = bgn = None
        for amount, currency in _PRICE_RE.findall(window):
            number = to_number(amount)
            if number is None:
                continue
            if currency.upper() == "EUR" and eur is None:
                eur = number
            elif currency.upper() != "EUR" and bgn is None:
                bgn = number
        if eur is None and bgn is None:
            continue
        return {
            "startingPriceEur": eur,
            "startingPriceBgn": bgn,
            "startingPriceRaw": clean(window),
        }


def _period(value: str) -> dict:
    m = _PERIOD_RE.search(str(value or ""))
    if not m:
        return {"biddingStart": None, "biddingEnd": None}
    return {"biddingStart": date_to_iso(m.group(1)), "biddingEnd": date_to_iso(m.group(2))}


def _area(value: str) -> dict:
    m = _AREA_RE.search(str(value or ""))
    if not m:
        return {"area": to_number(value), "areaUnit": None}
    return {"area": to_number(m.group(1)), "areaUnit": clean(m.group(2))}


def _build(property_id: str, fields: dict, page_text: str, input_value: str, source_url: str, extra: dict) -> dict:
    mapped = _map_fields(fields)
    record = _envelope(input_value, "AUCTION")
    record.update(
        {
            "propertyId": property_id,
            "url": source_url,
            "locality": mapped.get("locality"),
            "districtCourt": mapped.get("districtCourt"),
            "enforcementAgent": mapped.get("enforcementAgent"),
            "agentRegistrationNumber": mapped.get("agentRegistrationNumber"),
            "agentAddress": mapped.get("agentAddress"),
            "agentPhone": mapped.get("agentPhone"),
            "agentMobile": mapped.get("agentMobile"),
            "agentEmail": mapped.get("agentEmail"),
            "propertyType": mapped.get("propertyType"),
            "constructionType": mapped.get("constructionType"),
            "description": mapped.get("description"),
            "scannedAnnouncement": mapped.get("scannedAnnouncement"),
            "biddingPeriodRaw": mapped.get("biddingPeriodRaw"),
            **_period(mapped.get("biddingPeriodRaw") or ""),
            "announcementAt": datetime_to_iso(mapped.get("announcementRaw")),
            "announcementRaw": mapped.get("announcementRaw"),
            **_area(mapped.get("area") or ""),
            **_prices(page_text),
            **extra,
            # Everything the portal published, under its own labels.
            "fields": fields,
        }
    )
    return record


def parse_list(html: str, page: int) -> list[dict]:
    tree = HTMLParser(html)
    records = []
    seen = set()
    for link in tree.css('a[href^="/properties/"]'):
        href = link.attributes.get("href") or ""
        m = re.fullmatch(r"/properties/(\d+)", href)
        if not m:
            continue
        property_id = m.group(1)
        if property_id in seen:
            continue

        # Walk up to the card that holds this link's label groups.
        card = link.parent
        for _ in range(6):
            if card is None:
                break
            if card.css("div.label__group"):
                break
            card = card.parent
        if card is None:
            continue
        fields = parse_label_groups(card)
        if not fields:
            continue
        seen.add(property_id)
        records.append(
            _build(
                property_id,
                fields,
                clean(card.text()) or "",
                f"list:page={page}",
                f"{BASE}/properties/{property_id}",
                {"listPage": page, "detailFetched": False},
            )
        )
    return records


def parse_property(property_id: str, html: str) -> dict:
    tree = HTMLParser(html)
    container = tree.css_first("div.wrapper-single") or tree
    fields = parse_label_groups(container)
    if not fields:
        raise ValueError(
            f"property {property_id}: no label/value pairs found in {len(html)} bytes "
            f"-- the portal's layout may have changed."
        )
    # The price and publication date live in a summary column OUTSIDE
    # wrapper-single, so the price scan runs over the whole page. Parsing only
    # the inner block silently dropped every price in the first build.
    page_text = clean(tree.text()) or ""
    record = _build(
        property_id,
        fields,
        page_text,
        property_id,
        f"{BASE}/properties/{property_id}",
        {"detailFetched": True},
    )
    record["publishedAt"] = published_to_iso(page_text)
    if not record.get("propertyType"):
        record["propertyType"] = _breadcrumb_type(tree)
    return record


def _breadcrumb_type(tree) -> str | None:
    """Property category from the breadcrumb ("Имоти > Парцел с къща").

    The detail page repeats the category as a heading next to the price, but
    the breadcrumb is the one place it is always present.
    """
    crumbs = [clean(li.text()) for li in tree.css("ul.breadcrumb li")]
    crumbs = [c for c in crumbs if c and c.lower() not in ("имоти",)]
    return crumbs[-1] if crumbs else None


def total_pages(html: str) -> int | None:
    pages = [int(p) for p in re.findall(r"perpage=\d+&(?:amp;)?p=(\d+)", html)]
    return max(pages) if pages else None


def wrap_reference(url: str, ok: bool, detail: str, sample: dict | None = None) -> dict:
    record = _envelope("reference", "SURFACE")
    record.update({"url": url, "isAvailable": ok, "detail": detail, "sample": sample or {}})
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
