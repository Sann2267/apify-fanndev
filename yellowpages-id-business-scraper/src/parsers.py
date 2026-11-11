"""Extraction layer.

Priority follows the house rule JSON-LD > embedded state > HTML selectors:

  * Listing pages carry a JSON-LD ``LocalBusiness`` array **and** a set of
    ``<div id="comp_...">`` cards. The JSON-LD holds geo/description/website;
    the cards hold the entry id and the detail URL. Neither alone is complete,
    so they are merged on normalised name.
  * Profile pages carry one JSON-LD ``LocalBusiness`` plus a definition list
    with fields JSON-LD omits (phone types, founding year, legal form).
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from html import unescape
from typing import Any
from urllib.parse import unquote, urlsplit

from selectolax.parser import HTMLParser

from .client import UnexpectedShape
from .constants import CANONICAL_HOST, DATA_HOST

_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_CFEMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
_SUPPLIER_RE = re.compile(r"suppliers_list=(\d+)")
_PROFILE_ID_RE = re.compile(r"/profil-(\d+)-")
_PHONE_ENTRY_RE = re.compile(r"/phone-(\d+)-(\d+)-(.+?)-(IDEN[A-Za-z0-9]+)\.html")
_FACET_RE = re.compile(
    r"ahrefClick\(event,'(?P<href>[^']+)'\)[^>]*>\s*(?P<label>[^<]+?)\s*"
    r'<span class="facets-count fnumber" data-facets-count="(?P<count>\d+)"',
    re.S,
)
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def clean(text: str | None) -> str | None:
    """Collapse whitespace and decode entities; None for empties.

    selectolax already decodes entities in HTML text, but JSON-LD string values
    arrive double-escaped ("Convention &amp; Spa"), so unescape here to keep the
    two extraction paths producing identical strings — the listing merge keys on
    the name, and a stray `&amp;` would split one business into two rows.
    """
    if text is None:
        return None
    out = _WS_RE.sub(" ", unescape(text)).strip(" , ")
    return out or None


def decode_cf_email(hexstr: str) -> str | None:
    """Undo Cloudflare's email obfuscation (XOR with the leading key byte)."""
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except (ValueError, IndexError):
        return None


def _norm_name(name: str | None) -> str:
    return _WS_RE.sub(" ", (name or "")).strip().casefold()


def json_ld_blocks(html: str) -> list[Any]:
    """Every parseable JSON-LD document on the page."""
    out: list[Any] = []
    for raw in _LD_RE.findall(html):
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # the page ships a few hand-built blocks with trailing commas
    return out


def _local_businesses(html: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in json_ld_blocks(html):
        items = block if isinstance(block, list) else [block]
        for item in items:
            if isinstance(item, dict) and "LocalBusiness" in str(item.get("@type", "")):
                found.append(item)
    return found


def canonical_url(path_or_url: str | None) -> str | None:
    """Rewrite a data-host URL onto the yellowpages.id brand host."""
    if not path_or_url:
        return None
    parts = urlsplit(path_or_url)
    path = parts.path + (("?" + parts.query) if parts.query else "")
    return CANONICAL_HOST + path


def _flatten_address(addr: Any) -> dict[str, Any]:
    if not isinstance(addr, dict):
        return {}
    return {
        "street": clean(addr.get("streetAddress")),
        "locality": clean(addr.get("addressLocality")),
        "region": clean(addr.get("addressRegion")),
        "postalCode": clean(addr.get("postalCode")),
        "country": clean(addr.get("addressCountry")) or "Indonesia",
    }


def _flatten_geo(geo: Any) -> dict[str, Any]:
    if not isinstance(geo, dict):
        return {"latitude": None, "longitude": None}

    def num(v: Any) -> float | None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {"latitude": num(geo.get("latitude")), "longitude": num(geo.get("longitude"))}


# ---------------------------------------------------------------------------
# listing pages  (/listing/places/ and /places/<slug>[/<City>])
# ---------------------------------------------------------------------------
def parse_listing(html: str) -> list[dict[str, Any]]:
    """Merge JSON-LD businesses with their HTML cards into one row per entry."""
    if "results_page" not in html and "ld+json" not in html:
        raise UnexpectedShape(
            "listing page has neither a results container nor JSON-LD — "
            "the template almost certainly changed"
        )

    ld_by_name: dict[str, dict[str, Any]] = {}
    for item in _local_businesses(html):
        ld_by_name.setdefault(_norm_name(item.get("name")), item)

    tree = HTMLParser(html)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for card in tree.css("div.mdc-card[id^='comp_']"):
        entry_id = (card.attributes.get("id") or "")[len("comp_"):]
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        rows.append(_card_row(card, entry_id, ld_by_name))

    # JSON-LD entries with no rendered card (sponsored/overflow slots) still
    # carry full contact data — emit them rather than dropping the rows.
    for key, item in ld_by_name.items():
        if key and key not in {_norm_name(r["name"]) for r in rows}:
            rows.append(_ld_only_row(item))

    return rows


def _card_row(card: Any, entry_id: str, ld_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    link = card.css_first("h2.card__title a")
    name = clean(link.text()) if link else None
    href = link.attributes.get("href") if link else None
    ld = ld_by_name.get(_norm_name(name), {})

    # Two entry species share the listing:
    #   comp_<digits>      -> a claimed company page  /profil-<id>-<slug>.html
    #   comp_IDEN<digits>  -> a phone-book record     /phone-<cc>-<number>-...html
    is_company = entry_id.isdigit()
    company_id: str | None = entry_id if is_company else None
    phone_from_url: str | None = None
    category_slug: str | None = None

    if href:
        m_prof = _PROFILE_ID_RE.search(href)
        if m_prof:
            company_id = m_prof.group(1)
        m_phone = _PHONE_ENTRY_RE.search(href)
        if m_phone:
            phone_from_url = "+" + m_phone.group(2)
            category_slug = m_phone.group(3)

    # Merge the two address sources per field, not all-or-nothing: the card's
    # <address> usually carries locality/region but often omits the street and
    # postcode, while the JSON-LD block carries street/postcode but no region.
    address = _address_from_node(addr_node := card.css_first("address"))
    ld_address = _flatten_address(ld.get("address"))
    for field, value in ld_address.items():
        if not address.get(field) and value:
            address[field] = value

    desc_node = card.css_first("p.company-description")
    description = clean(desc_node.text()) if desc_node else clean(ld.get("description"))

    button = card.css_first("[data-cpk]")
    website = None
    lat = lng = None
    if button is not None:
        website = clean(button.attributes.get("data-cwebsite"))
        direct = button.attributes.get("data-cdirect") or ""
        if "," in direct:
            try:
                lat, lng = (float(x) for x in direct.split(",", 1))
            except ValueError:
                lat = lng = None

    geo = _flatten_geo(ld.get("geo"))
    if lat is not None:
        geo = {"latitude": lat, "longitude": lng}

    phone = clean(ld.get("telephone")) or phone_from_url
    emails = _emails_from_node(card)

    detail_url = href if href and href.startswith("http") else None
    return {
        "entryId": entry_id,
        "entryType": "COMPANY" if is_company else "PHONE_LISTING",
        "companyId": company_id,
        "name": name,
        "description": description,
        "phone": phone,
        "emails": emails,
        "website": website or clean(ld.get("url")),
        "categorySlug": category_slug,
        "address": address,
        "geo": geo,
        "image": clean(ld.get("image")),
        "detailUrl": detail_url,
        "yellowpagesUrl": canonical_url(detail_url),
    }


def _ld_only_row(item: dict[str, Any]) -> dict[str, Any]:
    target = ((item.get("potentialAction") or {}) or {}).get("target") or ""
    m = _SUPPLIER_RE.search(target if isinstance(target, str) else "")
    company_id = m.group(1) if m else None
    return {
        "entryId": company_id,
        "entryType": "COMPANY" if company_id else "LISTING",
        "companyId": company_id,
        "name": clean(item.get("name")),
        "description": clean(item.get("description")),
        "phone": clean(item.get("telephone")),
        "emails": [],
        "website": clean(item.get("url")),
        "categorySlug": None,
        "address": _flatten_address(item.get("address")),
        "geo": _flatten_geo(item.get("geo")),
        "image": clean(item.get("image")),
        "detailUrl": None,
        "yellowpagesUrl": None,
    }


def _address_from_node(node: Any) -> dict[str, Any]:
    if node is None:
        return {"street": None, "locality": None, "region": None, "postalCode": None, "country": None}
    out: dict[str, Any] = {}
    for prop in ("addressLocality", "addressRegion", "addressCountry", "postalCode", "streetAddress"):
        # itemprop casing is inconsistent in the template (`itemprop` on some
        # spans, `itemProp` on addressCountry), so match case-insensitively.
        hit = next(
            (s for s in node.css("span") if (s.attributes.get("itemprop") or "").lower() == prop.lower()),
            None,
        )
        out[prop] = clean(hit.text()) if hit else None

    # Listing cards put the street as a bare text tail after the spans rather
    # than in a span of its own. Take only the element's own text nodes —
    # string-replacing the span values out of the full text corrupts streets
    # that legitimately repeat the city name ("... Jakarta Selatan").
    street = out.get("streetAddress") or clean(node.text(deep=False))
    return {
        "street": street,
        "locality": out.get("addressLocality"),
        "region": out.get("addressRegion"),
        "postalCode": out.get("postalCode"),
        "country": out.get("addressCountry") or "Indonesia",
    }


def _emails_from_node(node: Any) -> list[str]:
    out: list[str] = []
    for m in _CFEMAIL_RE.findall(node.html or ""):
        dec = decode_cf_email(m)
        if dec and "@" in dec and dec not in out:
            out.append(dec)
    return out


def listing_has_results(html: str) -> bool:
    """Content-based stop condition.

    p=11 answers 200 with an intact shell and zero cards, so paging must stop on
    emptiness rather than on status code.
    """
    return bool(HTMLParser(html).css("div.mdc-card[id^='comp_']")) or bool(_local_businesses(html))


def parse_result_total(html: str) -> int | None:
    """The advertised hit count. Capped at 250 in practice — see MAX_PAGE."""
    m = re.search(r"(\d[\d.,]*)\s*(?:hasil|results)", html)
    if not m:
        return None
    try:
        return int(re.sub(r"[.,]", "", m.group(1)))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# company profile  (/profil-<id>-<slug>.html)
# ---------------------------------------------------------------------------
def parse_profile(html: str, url: str) -> dict[str, Any]:
    businesses = _local_businesses(html)
    tree = HTMLParser(html)

    title_node = tree.css_first("h1")
    name = clean(title_node.text()) if title_node else None
    ld = businesses[0] if businesses else {}
    if not name:
        name = clean(ld.get("name"))
    if not name:
        raise UnexpectedShape(f"no business name on profile page {url}")

    m = _PROFILE_ID_RE.search(url)
    company_id = m.group(1) if m else None
    pk = tree.css_first("[data-pk]")
    if pk is not None:
        company_id = pk.attributes.get("data-pk") or company_id

    phones = _profile_phones(tree, html)
    details = _definition_pairs(tree)

    site_node = tree.css_first("div.company-header-www a[href^='http']")
    website = site_node.attributes.get("href") if site_node is not None else None
    website = website or clean(ld.get("url"))

    categories = []
    for a in tree.css("a[href*='/places/']"):
        href = a.attributes.get("href") or ""
        slug = href.split("/places/")[-1].split("/")[0].split("?")[0]
        label = clean(a.text())
        if slug and slug not in [c["slug"] for c in categories]:
            categories.append({"slug": unquote(slug), "name": label})

    emails = _emails_from_node(tree.body) if tree.body else []

    return {
        "companyId": company_id,
        "name": name,
        "description": clean(ld.get("description")),
        "phones": phones,
        "phone": phones[0]["number"] if phones else clean(ld.get("telephone")),
        "emails": emails,
        "website": website,
        "address": _flatten_address(ld.get("address")),
        "geo": _flatten_geo(ld.get("geo")),
        "image": clean(ld.get("image")),
        "foundedYear": details.get("Tahun pendirian"),
        "legalForm": details.get("Bentuk hukum"),
        "activityForm": details.get("Formulir kegiatan"),
        "categories": categories,
        "detailUrl": url,
        "yellowpagesUrl": canonical_url(url),
    }


def _profile_phones(tree: Any, html: str) -> list[dict[str, Any]]:
    """Phone numbers with their labels.

    The header hides the number behind a 'click to reveal' button but ships it
    in ``data-number`` / ``data-phone-number``, so no interaction is needed. The
    detail table then repeats each number as a ``tel:`` link carrying its type.
    """
    out: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}

    def add(number: str | None, label: str | None) -> None:
        num = clean(number)
        if not num:
            return
        key = _digits(num)
        if not key:
            return
        if key in index:
            if label and not index[key]["label"]:
                index[key]["label"] = label
            return
        entry = {"number": num, "label": label}
        index[key] = entry
        out.append(entry)

    # Authoritative: the <dl> table, where each number carries its own label.
    for a in tree.css("a[href^='tel:']"):
        muted = a.css_first("span.text-muted")
        label = clean(muted.text()).strip("()") if muted is not None else None
        if muted is not None:
            muted.decompose()
        add(clean(a.text()) or (a.attributes.get("href") or "")[4:], label)

    # Fallback: the header attributes, for profiles with no detail table.
    for selector, attr in (("[data-number]", "data-number"),
                           ("[data-phone-number]", "data-phone-number")):
        for node in tree.css(selector):
            add(node.attributes.get(attr), None)

    return out


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _definition_pairs(tree: Any) -> dict[str, str]:
    """Label/value rows from the profile's ``<dl>`` detail table.

    Pairing is positional: a regex that scanned forward from the label text
    happily returned the *next* label when a field was blank (the site emits
    ``<dt>Formulir kegiatan</dt><dd></dd>``), so walk the element order instead.
    """
    out: dict[str, str] = {}
    for dl in tree.css("dl"):
        label: str | None = None
        for node in dl.iter():
            tag = node.tag
            if tag == "dt":
                label = clean(node.text())
            elif tag == "dd" and label:
                value = clean(node.text())
                if value:
                    out[label] = value
                label = None
    return out


# ---------------------------------------------------------------------------
# facets  (market insight)
# ---------------------------------------------------------------------------
def parse_facets(html: str) -> dict[str, Any]:
    """Region / city hit counts plus the 'Similar words' keyword expansion."""
    regions: list[dict[str, Any]] = []
    cities: list[dict[str, Any]] = []
    for m in _FACET_RE.finditer(html):
        href = m.group("href").replace("&amp;", "&")
        entry = {"name": clean(m.group("label")), "count": int(m.group("count"))}
        if "adm=" in href:
            entry["filterValue"] = href.split("adm=")[1].split("&")[0].replace("+", " ")
            regions.append(entry)
        elif "cty=" in href:
            entry["filterValue"] = href.split("cty=")[1].split("&")[0].replace("+", " ")
            cities.append(entry)

    similar: list[str] = []
    tree = HTMLParser(html)
    for block in tree.css("div.single-facetlist"):
        title = block.css_first("div.facet-title")
        if title and "Similar words" in (title.text() or ""):
            for a in block.css("a"):
                label = clean(a.text())
                if label and label not in similar:
                    similar.append(label)
    return {"regions": regions, "cities": cities, "similarKeywords": similar}


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------
def parse_products(html: str) -> list[dict[str, Any]]:
    """Product search rows.

    Product cards use ``id="obj_<productId>"`` — a different wrapper from the
    business listing's ``comp_`` cards — and link with relative hrefs.
    """
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for card in tree.css("div.mdc-card[id^='obj_']"):
        pid = (card.attributes.get("id") or "")[len("obj_"):]
        if not pid or pid in seen:
            continue
        seen.add(pid)

        link = card.css_first("h2 a[href*='/product-']")
        href = link.attributes.get("href") if link else None
        name = clean(link.text()) if link else None
        if not name and href:
            m = re.search(r"/product-(.*)_\d+\.html", href)
            name = unquote(m.group(1)).replace("-", " ").strip() if m else None

        company = card.css_first("a[href*='/profil-']")
        company_href = company.attributes.get("href") if company else None

        footer = card.css_first("div.product-card-footer")
        price_value = price_currency = location = None
        if footer is not None:
            right = footer.css_first("div.pull-right")
            if right is not None:
                raw = clean(right.text()) or ""
                m = re.search(r"([\d][\d.,]*)\s*([A-Za-z]{2,3})?", raw)
                if m:
                    price_value = m.group(1)
                    price_currency = m.group(2)
            left = footer.css_first("div.pull-left")
            if left is not None:
                # Material-icon <span>s render their ligature name ("place") as
                # text, so drop them before reading the label.
                for icon in left.css("span.material-icons"):
                    icon.decompose()
                location = clean(left.text())

        img = card.css_first("img[data-original]")
        tags = [clean(a.text()) for a in card.css("div.mdc-chip__text a")]

        # "Visit shop" buttons hide the merchant's real URL behind /r/<base64>.
        shop_url = None
        visit = card.css_first("a[href^='/r/']")
        if visit is not None:
            shop_url = _decode_redirect(visit.attributes.get("href") or "")

        out.append({
            "productId": pid,
            "name": name,
            "priceValue": price_value,
            "priceCurrency": price_currency,
            "location": location,
            "tags": [t for t in tags if t],
            "image": img.attributes.get("data-original") if img is not None else None,
            "shopUrl": shop_url,
            "companyName": clean(company.text()) if company else None,
            "companyId": (_PROFILE_ID_RE.search(company_href).group(1)
                          if company_href and _PROFILE_ID_RE.search(company_href) else None),
            "companyUrl": _abs(company_href),
            "detailUrl": _abs(href),
            "yellowpagesUrl": canonical_url(href),
        })

    if not out and "/product-" in html:
        raise UnexpectedShape(
            "product links are present but no obj_ cards matched — the product "
            "listing template changed"
        )
    return out


def products_have_results(html: str) -> bool:
    """Stop condition for the product listing (its cards are obj_, not comp_)."""
    return bool(HTMLParser(html).css("div.mdc-card[id^='obj_']"))


def _abs(href: str | None) -> str | None:
    if not href:
        return None
    return href if href.startswith("http") else DATA_HOST + href


def _decode_redirect(href: str) -> str | None:
    """/r/<urlsafe-base64>?... wraps the merchant's outbound URL."""
    token = href[len("/r/"):].split("?")[0]
    try:
        pad = "=" * (-len(token) % 4)
        return base64.urlsafe_b64decode(token + pad).decode("utf-8", "replace") or None
    except (binascii.Error, ValueError):
        return None


# ---------------------------------------------------------------------------
# geo directory  (/citymap-ID-<code>/)
# ---------------------------------------------------------------------------
def parse_citymap(html: str) -> list[dict[str, Any]]:
    """Cities under a province page."""
    out: list[dict[str, Any]] = []
    for a in HTMLParser(html).css("a[href*='/citymap-ID-']"):
        href = a.attributes.get("href") or ""
        m = re.search(r"/citymap-ID-(\d+)-([^/]+)/?$", href)
        if not m:
            continue
        out.append({
            "provinceCode": m.group(1),
            "city": unquote(m.group(2)).replace("+", " "),
            "url": href,
            "yellowpagesUrl": canonical_url(href),
        })
    return out


def parse_city_categories(html: str) -> list[dict[str, Any]]:
    """Category links exposed on a city page: /places/<slug>/<City>."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for a in HTMLParser(html).css("a[href*='/places/']"):
        href = a.attributes.get("href") or ""
        m = re.search(r"/places/([a-z0-9\-]+)/([^/?]+)$", href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append({
            "categorySlug": m.group(1),
            "categoryName": clean(a.text()),
            "city": unquote(m.group(2)).replace("-", " "),
            "url": href,
            "yellowpagesUrl": canonical_url(href),
        })
    return out
