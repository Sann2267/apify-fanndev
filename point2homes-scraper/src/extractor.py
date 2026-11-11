"""Parsing logic -- turns Point2Homes' JSON-LD blocks (+ a couple of
supplementary HTML data-attributes not present in JSON-LD) into
dataset-ready records.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming): every JSON-LD `RentAction` block (search-result
summary card, or full listing/apartment-complex detail page) is passed
through close to as-is -- `agent`, `priceSpecification`, `object`
(itself carrying `address`, `description`, `numberOfRooms`,
`numberOfBathroomsTotal`, `floorSize`, `accommodationFloorPlan`, ...).
A handful of fields that only exist as HTML `data-*` attributes (not in
JSON-LD at all -- geo-coordinates, Point2Homes' own internal numeric
IDs) are added as flat top-level extras since they're not upstream JSON
fields to preserve verbatim, just genuinely new data this actor adds.
"""

import json
import re
from datetime import datetime, timezone
from html import unescape

JSONLD_BLOCK_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
LOCATION_INFO_RE = re.compile(r'<span id="location-info"([^>]*)>', re.S)
DATA_ATTR_RE = re.compile(r'data-([a-zA-Z]+)="([^"]*)"')
GALLERY_RE = re.compile(r'<ul class="gallery-photos"[^>]*>(.*?)</ul>', re.S)
IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"')


class UnexpectedShape(Exception):
    """Upstream HTML/JSON-LD shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_jsonld_blocks(html: str) -> list[dict]:
    blocks = []
    for raw in JSONLD_BLOCK_RE.findall(html):
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # a malformed/unrelated block shouldn't sink the whole page
    return blocks


def extract_jsonld_by_type(html: str, type_name: str) -> dict | None:
    for block in _parse_jsonld_blocks(html):
        if block.get("@type") == type_name:
            return block
    return None


def extract_search_page(html: str) -> tuple[list[dict], int | None]:
    """Returns (list of raw RentAction dicts, numberOfItems total) for
    one search-results page."""
    item_list = extract_jsonld_by_type(html, "ItemList")
    if item_list is None:
        raise UnexpectedShape("ItemList JSON-LD block not found on search page -- shape has likely changed.")

    elements = item_list.get("itemListElement")
    if elements is None:
        raise UnexpectedShape("ItemList.itemListElement missing -- shape has likely changed.")

    items = []
    for el in elements:
        item = el.get("item")
        if item is None:
            continue
        record = dict(item)
        record["position"] = el.get("position")
        items.append(record)

    return items, item_list.get("numberOfItems")


def extract_location_info(html: str) -> dict | None:
    """Parses `<span id="location-info" data-*="...">` -- carries
    geo-coordinates and Point2Homes' own internal numeric IDs, none of
    which appear anywhere in the page's JSON-LD."""
    m = LOCATION_INFO_RE.search(html)
    if not m:
        return None
    attrs = dict(DATA_ATTR_RE.findall(m.group(1)))
    if not attrs:
        return None

    def _num(key):
        val = attrs.get(key)
        if val in (None, ""):
            return None
        try:
            return float(val) if "." in val else int(val)
        except ValueError:
            return val

    return {
        "geoId": _num("geoid"),
        "latitude": _num("latitude"),
        "longitude": _num("longitude"),
        "internalId": _num("id"),
        "companyId": _num("companyId") or _num("companyid"),
        "propertyShortName": attrs.get("propertyshortname"),
        "city": attrs.get("city"),
        "state": attrs.get("state"),
        "country": attrs.get("country"),
    }


def extract_gallery_photos(html: str) -> list[str]:
    m = GALLERY_RE.search(html)
    if not m:
        return []
    srcs = IMG_SRC_RE.findall(m.group(1))
    return [unescape(s) for s in srcs if "no-image.png" not in s]


def wrap(item: dict, input_value: str, source: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_listing_detail(html: str, input_value: str) -> dict | None:
    """Full listing/apartment-complex detail page -- the JSON-LD
    `RentAction` block plus the HTML-only geo/ID supplement and photo
    gallery. Returns None if the page 200'd but carries no RentAction
    block (observed on removed/expired listings that still resolve)."""
    rent_action = extract_jsonld_by_type(html, "RentAction")
    if rent_action is None:
        return None

    record = dict(rent_action)
    record.pop("@context", None)

    location_info = extract_location_info(html)
    if location_info:
        record.update(location_info)

    photos = extract_gallery_photos(html)
    if photos:
        record["photos"] = photos

    return record
