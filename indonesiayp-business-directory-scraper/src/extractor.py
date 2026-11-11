"""HTML parsing + record shaping.

Listing cards are parsed from `div.company[data-cmpid]`; company pages are
parsed from their schema.org `LocalBusiness` JSON-LD (name, address, phone,
website, lat/lng, rating) **plus** the label/value blocks that carry what
the JSON-LD omits (mobile phone, working hours, manager, establishment
year, employee band, description, categories).

Both parsers degrade field-by-field: a missing block yields a null field,
never an exception.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL

_WS = re.compile(r"\s+")
_RATING = re.compile(r"\b([0-5](?:\.[0-9])?)\s+([0-9,]+)\s+Reviews?\b", re.I)
_YEARS_WITH_US = re.compile(r"\+?([0-9]{1,2})\s*Years? with us", re.I)
_ESTABLISHED = re.compile(r"\b((?:18|19|20)[0-9]{2})\s*Established\b", re.I)
_PHOTOS = re.compile(r"\b([0-9]+)\s*Photos?\b", re.I)
_PHONE = re.compile(r"^[\d\s()+\-]{6,}$")
_COMPANY_URL = re.compile(r"/company/(\d+)/([^/?#]+)")


def _txt(node) -> str:
    return _WS.sub(" ", node.get_text(" ", strip=True)).strip() if node else ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def company_path_from_input(raw: str) -> str:
    """Accepts a full company URL, a `/company/<id>/<slug>` path, or a bare
    numeric id, and returns the path to fetch."""
    s = (raw or "").strip()
    m = _COMPANY_URL.search(s)
    if m:
        return f"/company/{m.group(1)}/{m.group(2)}"
    if s.isdigit():
        # The slug segment is cosmetic -- upstream resolves on the id alone.
        return f"/company/{s}/x"
    return ""


def parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("div.company[data-cmpid]"):
        link = card.select_one('div.company_header h3 a[href*="/company/"]')
        href = link.get("href") if link else None
        if href and href.startswith("/"):
            href = f"{BASE_URL}{href}"
        text = _txt(card)
        rating = _RATING.search(text)
        years = _YEARS_WITH_US.search(text)
        est = _ESTABLISHED.search(text)
        photos = _PHOTOS.search(text)

        # The phone sits in a `div.s` next to a phone icon; the same block
        # shape is reused for "2012 Established", "E-mail", "Map" etc, so the
        # icon's aria-label is what identifies it.
        phone = None
        for block in card.select("div.s"):
            icon = block.select_one("i[aria-label]")
            if icon and icon.get("aria-label") == "Phone number":
                candidate = _txt(block)
                phone = candidate if _PHONE.match(candidate) else candidate or None
                break

        address = _txt(card.select_one("div.address"))
        city_node = card.select_one("div.address b")
        out.append(
            {
                "companyId": card.get("data-cmpid"),
                "name": _txt(link) or None,
                "profileUrl": href,
                "address": address or None,
                "city": _txt(city_node) or None,
                "phone": phone,
                "isVerified": bool(card.select_one("u.v")),
                "yearsListed": _int(years.group(1)) if years else None,
                "establishedYear": _int(est.group(1)) if est else None,
                "rating": _float(rating.group(1)) if rating else None,
                "reviewCount": _int(rating.group(2)) if rating else None,
                "photoCount": _int(photos.group(1)) if photos else None,
                "hasWebsite": "Website" in text,
                "hasEmail": "E-mail" in text,
            }
        )
    return out


def _jsonld_local_business(soup) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "LocalBusiness":
                return item
    return {}


def _info_fields(soup) -> dict:
    """The detail page renders each attribute as
    `<div class="info"><div class="label">Website address</div>value</div>`.
    Labels are the stable key -- their order and presence vary per listing,
    and the leading label text is repeated inside the block's own text, so it
    is stripped off the value."""
    fields = {}
    for block in soup.select("div.info"):
        label_node = block.select_one("div.label")
        if not label_node:
            continue
        label = _txt(label_node)
        value = _txt(block)
        if value.startswith(label):
            value = value[len(label):].strip()
        if label and value:
            fields.setdefault(label, value)
    return fields


def parse_company(html: str, profile_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    ld = _jsonld_local_business(soup)
    info = _info_fields(soup)
    address = ld.get("address") or {}
    geo = ld.get("geo") or {}
    rating = ld.get("aggregateRating") or {}

    m = _COMPANY_URL.search(profile_url)
    categories = info.get("Listed in categories")

    return {
        "companyId": m.group(1) if m else None,
        "name": ld.get("name") or _txt(soup.select_one("h1")) or None,
        "profileUrl": ld.get("@id") or profile_url,
        "streetAddress": address.get("streetAddress"),
        "city": address.get("addressLocality"),
        "region": address.get("addressRegion"),
        "country": address.get("addressCountry"),
        "addressText": info.get("Address"),
        "phone": ld.get("telephone") or info.get("Contact number"),
        "mobilePhone": info.get("Mobile phone"),
        "website": ld.get("url") or info.get("Website address"),
        "latitude": _float(geo.get("latitude")),
        "longitude": _float(geo.get("longitude")),
        "rating": _float(rating.get("ratingValue")),
        "reviewCount": _int(rating.get("reviewCount")),
        "workingHours": info.get("Working hours"),
        "manager": info.get("Company manager"),
        "establishedYear": _int(info.get("Establishment year")),
        "employees": info.get("Employees"),
        "description": info.get("Company description"),
        "categories": categories,
        "imageUrl": ld.get("image"),
    }


def wrap(item: dict, input_value: str, source: str = "S1-html", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
