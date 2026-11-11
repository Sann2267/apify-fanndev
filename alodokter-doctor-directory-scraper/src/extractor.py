"""JSON-LD extraction + record shaping.

Every listing page embeds a schema.org `ItemList` whose members are full
`Physician` objects, so no CSS-selector scraping is needed for the listing
-- the parse reads structured data straight out of the page.

### Gotcha: upstream emits invalid JSON for names containing an apostrophe

A doctor called *drg. Lu'lu Ul Muhimmah* is written into the JSON-LD as

    "name": "drg. Lu\\&#39;lu Ul Muhimmah"

i.e. the apostrophe is first JS-escaped (`\'`) and then HTML-encoded
(`&#39;`), leaving the sequence `\&` -- which is not a legal JSON escape.
`json.loads` therefore raises "Invalid \\escape" and the **entire** listing
is lost. This is not an edge case: it silently emptied the whole
`dokter-gigi` specialty (307 KB of real content, zero records) in the first
build. `loads_lenient` repairs the sequence before parsing, and names are
HTML-unescaped afterwards.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL

_WS = re.compile(r"\s+")
_PROFILE_SLUG = re.compile(r"/cari-dokter/([^/?#]+)")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def loads_lenient(raw: str):
    """json.loads, with a repair pass for the `\\&#39;` defect described in
    the module docstring. Returns None when the payload is unusable."""
    for attempt in (raw, raw.replace("\\&", "&")):
        try:
            return json.loads(attempt)
        except (ValueError, TypeError):
            continue
    return None


def _clean(value):
    if isinstance(value, str):
        return _WS.sub(" ", html.unescape(value)).strip()
    return value


def _ld_nodes(soup):
    for script in soup.select('script[type="application/ld+json"]'):
        data = loads_lenient(script.string or script.get_text() or "")
        if data is None:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        for node in (graph or (data if isinstance(data, list) else [data])):
            if isinstance(node, dict):
                yield node


def _address_list(node) -> list[dict]:
    addr = node.get("address")
    if isinstance(addr, dict):
        addr = [addr]
    out = []
    for a in addr or []:
        if isinstance(a, dict):
            out.append(
                {
                    "streetAddress": _clean(a.get("streetAddress")),
                    "locality": _clean(a.get("addressLocality")),
                    "region": _clean(a.get("addressRegion")),
                    "country": _clean(a.get("addressCountry")),
                }
            )
    return out


def _first_dict(value) -> dict:
    """Upstream types the same property differently on the two page kinds:
    a listing card carries `worksFor` / `makesOffer` as a single object,
    while a profile page carries them as a **list** (a doctor practising at
    several hospitals, with one offer per hospital). Reading `.get` on the
    list form raised AttributeError and killed the whole profile parse, so
    every such property is funnelled through here; the full list is still
    emitted separately (`hospitals`, `offers`).
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _all_dicts(value) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []


def _physician_record(node: dict) -> dict:
    works_all = _all_dicts(node.get("worksFor"))
    offers_all = _all_dicts(node.get("makesOffer"))
    works = _first_dict(node.get("worksFor"))
    offer = _first_dict(node.get("makesOffer"))
    rating = _first_dict(node.get("aggregateRating"))
    extra = {}
    for prop in node.get("additionalProperty") or []:
        if isinstance(prop, dict) and prop.get("name"):
            extra[prop["name"]] = _clean(prop.get("value"))

    url = _clean(node.get("url")) or ""
    slug_match = _PROFILE_SLUG.search(url)
    price = offer.get("price")

    return {
        "name": _clean(node.get("name")),
        "slug": slug_match.group(1) if slug_match else None,
        "profileUrl": url or None,
        "specialty": _clean(node.get("medicalSpecialty")),
        "specialtyLabel": _clean(node.get("alternateName")),
        "hospital": _clean(works.get("name")),
        "hospitalAddress": _clean(_first_dict(works.get("address")).get("streetAddress")),
        "hospitals": [
            {
                "name": _clean(w.get("name")),
                "address": _clean(_first_dict(w.get("address")).get("streetAddress")),
            }
            for w in works_all
        ]
        or None,
        "offers": [
            {
                "name": _clean(o.get("name")),
                "price": int(o["price"]) if str(o.get("price") or "").isdigit() else None,
                "currency": _clean(o.get("priceCurrency")),
            }
            for o in offers_all
        ]
        or None,
        "addresses": _address_list(node) or None,
        "consultationPrice": int(price) if str(price or "").isdigit() else None,
        "priceCurrency": _clean(offer.get("priceCurrency")),
        "rating": _clean(rating.get("ratingValue")),
        "reviewCount": int(str(rating.get("reviewCount") or "0").replace(",", ""))
        if str(rating.get("reviewCount") or "").replace(",", "").isdigit()
        else None,
        "nextSchedule": extra.get("next_schedule"),
        "imageUrl": _clean(node.get("image")),
        "description": _clean(node.get("description")),
    }


def parse_listing(page_html: str) -> list[dict]:
    """Return one record per doctor in the page's ItemList."""
    soup = BeautifulSoup(page_html, "lxml")
    out = []
    for node in _ld_nodes(soup):
        if node.get("@type") != "ItemList":
            continue
        for element in node.get("itemListElement") or []:
            item = element.get("item") if isinstance(element, dict) else None
            if isinstance(item, dict) and item.get("@type") == "Physician":
                record = _physician_record(item)
                record["listName"] = _clean(node.get("name"))
                out.append(record)
    return out


def parse_profile(page_html: str, profile_url: str) -> dict:
    soup = BeautifulSoup(page_html, "lxml")
    for node in _ld_nodes(soup):
        if node.get("@type") == "Physician":
            record = _physician_record(node)
            record.setdefault("profileUrl", profile_url)
            return record
    return {}


def profile_path_from_input(raw: str) -> str:
    """Accepts a full profile URL or a bare doctor slug."""
    s = (raw or "").strip().split("?")[0].split("#")[0].rstrip("/")
    s = re.sub(r"^https?://(?:www\.)?alodokter\.com", "", s, flags=re.I)
    if s.startswith("/cari-dokter/"):
        return s
    s = s.lstrip("/")
    return f"/cari-dokter/{s}" if s else ""


def wrap(item: dict, input_value: str, source: str = "S1-jsonld", record_type: str | None = None) -> dict:
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


def city_slugs(page_html: str, specialty: str) -> list[str]:
    return sorted(
        set(re.findall(rf'/cari-dokter/{re.escape(specialty)}/([a-z0-9\-]+)"', page_html))
    )


def absolute(path: str) -> str:
    return path if path.startswith("http") else f"{BASE_URL}{path}"
