"""Shaping indotrading.com pages into dataset records.

The raw-passthrough rule applies as far as an HTML site allows it: there is no
upstream JSON shape to preserve for the listing pages, so field names follow
the labels indotrading itself prints (tahunBerdiri, statusPajak, bidangUsaha)
rather than being translated. Where the page carries a machine value and a
display value for the same thing -- priceRaw from data-rfq-price next to
priceText from the rendered label -- both are emitted, because they disagree
often enough that picking one would be a silent decision.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterator

from selectolax.parser import HTMLParser, Node

from .constants import SITE_ROOT

log = logging.getLogger("indotrading.parsers")

# "(Halaman 3 dari 16)" -- the second number OVERSTATES reachable inventory and
# is kept as metadata only. See constants.MAX_PAGE_HARD_CAP.
RE_PAGE_COUNTER = re.compile(r"Halaman\s+(\d+)\s+dari\s+(\d+)", re.I)
# "Menampilkan 4.004 Produk untuk ..." -- Indonesian digit grouping uses dots.
RE_TOTAL_PRODUCTS = re.compile(r"Menampilkan\s+([\d.,]+)\s+Produk", re.I)
# "1939 supplier Pompa ditemukan"
RE_TOTAL_SUPPLIERS = re.compile(r"([\d.,]+)\s+supplier\b", re.I)
# Product ids are the -p<digits> tail of the product URL.
RE_PRODUCT_ID_IN_URL = re.compile(r"-p(\d+)\.aspx", re.I)
# /company_<slug>_<categoryId>/
RE_COMPANY_DIR_URL = re.compile(r"/company_([a-z0-9\-]+)_(\d+)/?", re.I)

MEMBERSHIP_TIERS = ("diamond", "platinum", "gold", "silver", "free")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(
    input_value: str,
    source: str,
    record_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }
    if payload:
        rec.update(payload)
    return rec


def error_record(
    input_value: str, error: str, detail: str = "", source: str = "none"
) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": "error",
        "_error": error,
        "_errorDetail": detail,
    }


# -- small helpers ---------------------------------------------------------


def _text(node: Node | None, sel: str | None = None) -> str | None:
    if node is None:
        return None
    target = node.css_first(sel) if sel else node
    if target is None:
        return None
    value = target.text(strip=True)
    return value or None


def _attr(node: Node | None, sel: str, attr: str) -> str | None:
    if node is None:
        return None
    target = node.css_first(sel)
    if target is None:
        return None
    value = target.attributes.get(attr)
    return value or None


def _abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return SITE_ROOT + href


def _int_id(text: str | None) -> int | None:
    """Indonesian digit grouping: 4.004 means four thousand and four."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _membership_tier(node: Node | None) -> str | None:
    """Read the paid-tier name off the badge element's class list.

    Scope matters: the logged-out page header carries one hidden badge for
    every tier (free, platinum, diamond) as templates for the member menu, so
    a document-wide query returns tiers that have nothing to do with the
    company on the page. Callers pass the company block, never the document.
    """
    if node is None:
        return None
    badge = node.css_first(".membership-supplier")
    if badge is None:
        return None
    classes = (badge.attributes.get("class") or "").lower().split()
    for tier in MEMBERSHIP_TIERS:
        if tier in classes:
            return tier
    return None


def listing_meta(html: str) -> dict[str, Any]:
    """Counters printed above a listing.

    `advertisedPages` is recorded but deliberately NOT used to drive
    pagination: recon found /jual-pressure-washer advertising 16 pages while
    running dry at 12, and /jual-mesin-las advertising 79 while empty by 50.
    """
    counter = RE_PAGE_COUNTER.search(html)
    total = RE_TOTAL_PRODUCTS.search(html)
    suppliers = RE_TOTAL_SUPPLIERS.search(html)
    return {
        "currentPage": int(counter.group(1)) if counter else None,
        "advertisedPages": int(counter.group(2)) if counter else None,
        "advertisedTotalProducts": _int_id(total.group(1)) if total else None,
        "advertisedTotalSuppliers": _int_id(suppliers.group(1)) if suppliers else None,
    }


# -- product cards (category listings and product search) ------------------


def parse_product_cards(html: str) -> list[dict[str, Any]]:
    """Cards on /jual-<slug> and /searchkeyword.aspx.

    Both surfaces render the identical `.k-product-card` component, which is
    why category and keyword search share one parser.
    """
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []

    for card in tree.css(".k-product-card"):
        # The encrypted product id that the contact endpoint takes. The
        # obvious place to read it is the WhatsApp button, but that button is
        # rendered for only 18 of 40 cards -- and the contact endpoint answers
        # with a WhatsApp number for the other 22 anyway, so its absence is a
        # UI decision about which seller tiers get a WhatsApp CTA, not missing
        # data. Reading data-enc-pid from whichever button carries it (the
        # phone button always does) takes contact coverage from 45% to 100%.
        wa = card.css_first(".showWa") or card.css_first("[data-enc-pid]")
        rfq = card.css_first("[data-rfq-pid]")
        wa_attrs = dict(wa.attributes) if wa else {}
        rfq_attrs = dict(rfq.attributes) if rfq else {}

        link = _attr(card, "a.new-link-prod", "href") or _attr(
            card, ".k-product-card-item-title", "href"
        )
        if not link:
            title_link = card.css_first(".tooltiptext a")
            link = title_link.attributes.get("href") if title_link else None

        product_url = _abs_url(link)
        product_id = rfq_attrs.get("data-rfq-pid") or wa_attrs.get("prodid")
        if not product_id and product_url:
            match = RE_PRODUCT_ID_IN_URL.search(product_url)
            product_id = f"P{match.group(1)}" if match else None

        company_block = card.css_first(".k-company-card-info")
        # The supplier link is the anchor wrapping that block. It cannot be
        # selected by href shape, because the product link is also a bare
        # "/..." path -- the difference is what the anchor contains.
        company_url = None
        for anchor in card.css("a"):
            if anchor.css_first(".k-company-card-info") is not None:
                company_url = _abs_url(anchor.attributes.get("href"))
                break

        brand = None
        for node in card.css(".fs-12"):
            value = node.text(strip=True)
            if value.lower().startswith("merek:"):
                brand = value.split(":", 1)[1].strip() or None
                break

        # Location and tax status sit as bare spans inside the company block;
        # the tax label is the only one of the pair that is predictable.
        location = None
        tax_status = None
        if company_block is not None:
            spans = [s.text(strip=True) for s in company_block.css("span")]
            spans = [s for s in spans if s]
            for idx, value in enumerate(spans):
                if value.lower().startswith("status pajak"):
                    tax_status = spans[idx + 1] if idx + 1 < len(spans) else None
                elif "," in value and not value.lower().startswith("status"):
                    location = value

        out.append(
            {
                "productId": product_id,
                "productUrl": product_url,
                "productName": (
                    _text(card, ".k-product-card-item-title")
                    or rfq_attrs.get("data-rfq-name")
                ),
                "imageUrl": _attr(card, "a.new-link-prod img", "src")
                or rfq_attrs.get("data-rfq-img"),
                # priceText is what a buyer sees; priceRaw is the number behind
                # the RFQ button. They disagree whenever the seller hid the
                # price, in which case the page prints "Minta penawaran" over a
                # placeholder number, so neither one alone is trustworthy.
                "priceText": _text(card, ".k-price"),
                "priceRaw": rfq_attrs.get("data-rfq-price"),
                "priceUnit": rfq_attrs.get("data-rfq-unit"),
                "isWholesale": rfq_attrs.get("data-rfq-grosir"),
                "brand": brand,
                "descriptionSnippet": _text(card, "p.text-break"),
                # PDN = "Produk Dalam Negeri", the Indonesian local-content
                # badge that government procurement filters on.
                "isPdn": any(
                    n.text(strip=True) == "PDN" for n in card.css(".text--orange")
                ),
                "companyId": rfq_attrs.get("data-rfq-cid")
                or wa_attrs.get("compid")
                or _text(card, ".compId"),
                "companyName": rfq_attrs.get("data-rfq-companyname")
                or wa_attrs.get("data-company-name")
                or _text(card, ".k-company-card-title"),
                "companyUrl": company_url,
                "companyLocation": location,
                "companyTaxStatus": tax_status,
                "membershipTier": _membership_tier(card),
                "membershipYears": _text(card, ".membership-year"),
                "isVerifiedSupplier": card.css_first(".k-company__verified") is not None,
                # Encrypted ids. secureProductId is the only key the contact
                # endpoint accepts; the plain P-number is rejected.
                "secureProductId": wa_attrs.get("data-enc-pid"),
                "secureCompanyId": wa_attrs.get("data-enc-cid"),
            }
        )
    return out


# -- product cards on a supplier profile -----------------------------------


def parse_supplier_product_cards(html: str) -> list[dict[str, Any]]:
    """Cards inside #productGridList on a supplier profile.

    A different component from the category card: it carries the category name
    and last-update date that the category card omits, but no encrypted
    product id, so contact enrichment is not available from this surface.
    """
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []

    for card in tree.css(".newProd"):
        rfq = card.css_first("[data-rfq-pid]")
        attrs = dict(rfq.attributes) if rfq else {}
        link = _attr(card, "h3 a", "href") or _attr(card, "a", "href")
        product_url = _abs_url(link)
        product_id = attrs.get("data-rfq-pid")
        if not product_id and product_url:
            match = RE_PRODUCT_ID_IN_URL.search(product_url)
            product_id = f"P{match.group(1)}" if match else None

        out.append(
            {
                "productId": product_id,
                "productUrl": product_url,
                "productName": _text(card, "h3 a") or attrs.get("data-rfq-name"),
                "imageUrl": _attr(card, "img", "src") or attrs.get("data-rfq-img"),
                "priceText": _text(card, ".price"),
                "priceRaw": attrs.get("data-rfq-price"),
                "priceUnit": attrs.get("data-rfq-unit"),
                "categoryName": _text(card, ".category .text-end"),
                "lastUpdate": _text(card, ".date-update"),
                "minOrder": _text(card, ".min-order div:nth-child(2)"),
                "companyId": attrs.get("data-rfq-cid"),
                "companyName": attrs.get("data-rfq-companyname"),
            }
        )
    return out


# -- company cards (supplier directory) ------------------------------------


def parse_company_cards(html: str) -> list[dict[str, Any]]:
    """Cards on /company_<slug>_<categoryId>/."""
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []

    for card in tree.css(".k-company-card-list-item"):
        slug = _attr(card, "a.product_title", "href")
        info_rows: dict[str, str] = {}
        for row in card.css(".info-row"):
            label = _text(row, ".label")
            value = _text(row, ".value")
            if label:
                info_rows[label.rstrip(" :")] = value or ""

        out.append(
            {
                "companyName": _text(card, "a.product_title"),
                "companySlug": (slug or "").lstrip("/") or None,
                "companyUrl": _abs_url(slug),
                "logoUrl": _attr(card, "img", "src"),
                "membershipTier": _membership_tier(card),
                "membershipYears": _text(card, ".membership-year"),
                "isVerifiedSupplier": card.css_first(".k-company__verified") is not None,
                # Rendered server-side here as "Online 1 Hari Lalu", unlike the
                # product cards where the same fact arrives from the API.
                "lastLoginText": _text(card, ".info-row-lastlog"),
                "taxStatus": info_rows.get("Status Pajak"),
                "about": _text(card, "p.line-clamp-5"),
                "infoRows": info_rows or None,
            }
        )
    return out


# -- supplier profile ------------------------------------------------------


def parse_supplier_profile(html: str, page_url: str) -> dict[str, Any]:
    """The company header and profile table on /<company-slug>."""
    tree = HTMLParser(html)
    # Every membership and verification badge is scoped to #comproHeader: the
    # page chrome above it holds hidden copies of all of them.
    header = tree.css_first("#comproHeader")

    info: dict[str, str] = {}
    profile_block = tree.css_first(".profile-info")
    if profile_block is not None:
        labels = profile_block.css(".w-30")
        values = profile_block.css(".w-70")
        for label, value in zip(labels, values):
            key = label.text(strip=True)
            if key:
                info[key] = value.text(strip=True)

    company_info = [n.text(strip=True) for n in header.css(".company-info")] if header else []
    location = None
    tax_status = None
    for value in company_info:
        if value.lower().startswith("status pajak"):
            tax_status = value.split(":", 1)[-1].strip() or None
        elif value:
            location = value

    verified_labels = [n.text(strip=True) for n in header.css(".text-verified")] if header else []
    # "Verified Supplier" is the flag; the sibling label lists which documents
    # were checked, e.g. "NPWP, SIUP".
    documents = [v for v in verified_labels if v and v != "Verified Supplier"]

    return {
        "companyName": _text(tree, "h1"),
        "companyUrl": page_url,
        "companySlug": page_url.rstrip("/").rsplit("/", 1)[-1] or None,
        "location": location,
        "taxStatus": tax_status,
        "lastLoginText": _text(header, ".company-info-info") if header else None,
        "membershipTier": _membership_tier(header),
        "membershipYears": _text(header, ".membership-year") if header else None,
        "isVerifiedSupplier": "Verified Supplier" in verified_labels,
        "verifiedDocuments": documents or None,
        "yearEstablished": info.get("Tahun Berdiri"),
        "address": info.get("Alamat"),
        "employeeCount": info.get("Jumlah Karyawan"),
        "businessFields": info.get("Bidang Perusahaan"),
        "sells": info.get("Kami Menjual"),
        "description": _text(tree, "#compro-desc-id"),
        "profileFields": info or None,
    }


# -- product detail --------------------------------------------------------


def _json_ld_blocks(tree: HTMLParser) -> Iterator[Any]:
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except ValueError:
            log.warning("Unparseable ld+json block (%d chars)", len(raw))


def parse_product_detail(html: str, page_url: str) -> dict[str, Any]:
    """A product page, preferring JSON-LD over the rendered markup.

    JSON-LD first per the stability order: indotrading restyles the product
    page far more often than it changes its schema.org output, and the Product
    node already carries name, description, image, price, currency,
    availability and seller.
    """
    tree = HTMLParser(html)

    product: dict[str, Any] = {}
    store: dict[str, Any] = {}
    breadcrumbs: list[dict[str, Any]] = []

    for block in _json_ld_blocks(tree):
        nodes = block if isinstance(block, list) else [block]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type")
            if node_type == "Product":
                product = node
            elif node_type == "Store":
                store = node
            elif node_type == "BreadcrumbList":
                for item in node.get("itemListElement") or []:
                    entry = item.get("item")
                    if isinstance(entry, dict):
                        breadcrumbs.append(
                            {"name": entry.get("name"), "url": entry.get("@id")}
                        )
                    elif item.get("name"):
                        breadcrumbs.append({"name": item.get("name"), "url": None})

    # The attribute list under the price: Stok, Negara Asal, Dikirim Dari,
    # Kategori, Update Terakhir. Labels vary by product, so read them as pairs
    # rather than by position.
    attributes: dict[str, str] = {}
    for row in tree.css(".tabpanel li.row"):
        spans = row.css("span, div")
        if len(spans) >= 2:
            key = spans[0].text(strip=True)
            value = spans[1].text(strip=True)
            if key and value:
                attributes[key] = value

    offers = product.get("offers") or {}
    seller = offers.get("seller") or {}
    match = RE_PRODUCT_ID_IN_URL.search(page_url)

    gallery = [
        node.attributes.get("data-src")
        for node in tree.css(".js-thumb[data-type='image']")
        if node.attributes.get("data-src")
    ]
    videos = [
        node.attributes.get("data-thumb")
        for node in tree.css(".js-thumb[data-type='video']")
        if node.attributes.get("data-thumb")
    ]

    return {
        "productId": f"P{match.group(1)}" if match else None,
        "productUrl": page_url,
        "productName": product.get("name") or _text(tree, "#productTitle"),
        "description": product.get("description"),
        "imageUrl": product.get("image"),
        "galleryImages": gallery or None,
        "youtubeVideoIds": videos or None,
        "priceText": _text(tree, "#price"),
        "price": offers.get("price"),
        "priceCurrency": offers.get("priceCurrency"),
        "availability": offers.get("availability"),
        "stock": attributes.get("Stok") or _text(tree, "#stock"),
        "countryOfOrigin": attributes.get("Negara Asal"),
        "shipsFrom": attributes.get("Dikirim Dari"),
        "categoryName": attributes.get("Kategori"),
        "lastUpdate": attributes.get("Update Terakhir"),
        "minimumOrder": _text(tree, ".d-flex.a-center.mb-4 h3"),
        "isPdn": "PDN" in (html[:200000] or "") and bool(tree.css(".flex-badge-wrapper")),
        "companyName": seller.get("name") or store.get("name"),
        "companyLogo": store.get("image"),
        "companyLocation": (store.get("address") or {}).get("addressLocality"),
        "companyId": _attr(tree, "[data-rfq-cid]", "data-rfq-cid"),
        "secureProductId": _attr(tree, "[data-enc-pid]", "data-enc-pid"),
        "breadcrumbs": breadcrumbs or None,
        "productAttributes": attributes or None,
    }


# -- category tree ---------------------------------------------------------


def parse_category_tree(html: str) -> list[dict[str, Any]]:
    """Every /jual-<slug> link on /productcatalog.

    One request returns the whole catalogue -- 4,009 slugs at recon time --
    which makes this the cheapest seed for a full-site crawl.
    """
    tree = HTMLParser(html)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for anchor in tree.css("a[href^='/jual-']"):
        href = anchor.attributes.get("href") or ""
        slug = href.strip("/")
        if not slug or slug in seen or "/" in slug:
            continue
        seen.add(slug)
        out.append(
            {
                "categorySlug": slug,
                "categoryName": anchor.text(strip=True) or None,
                "categoryUrl": _abs_url(href),
            }
        )
    return out


def company_directory_ids(final_url: str) -> dict[str, Any]:
    """Pull the slug and numeric category id out of a /company_..._<id>/ URL."""
    match = RE_COMPANY_DIR_URL.search(final_url)
    if not match:
        return {"categorySlug": None, "categoryId": None}
    return {"categorySlug": match.group(1), "categoryId": int(match.group(2))}
