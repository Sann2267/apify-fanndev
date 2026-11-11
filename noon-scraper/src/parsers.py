"""Payload extraction and the dataset envelope.

Two response shapes have to be handled, because noon runs two catalogues:

  Marketplace (`mp-customer-catalog-api`)
      A flat `hits` array. Search, category and brand pages are all the SAME
      shape -- one extractor covers all three.

  noon Minutes (`/_svc/catalog`)
      A CMS layout. `hits` is ALWAYS an empty array here, which reads as "no
      results" if you assume the marketplace shape; the products are really at
      `results[].modules[] where type == "instantPLPItem" -> data.product`,
      interleaved with ad banners. Recon hit this exact trap: the same query
      looked like 0 results and 814 nbHits at the same time.

Raw passthrough is the rule (see .ai/conventions/dataset-envelope.md): upstream
field names are emitted verbatim and nothing is renamed. The actor adds only
the `_`-prefixed envelope plus `currency`/`country`/`locale`, because the API
returns bare numbers with no currency anywhere in the payload -- a price of
4899 is meaningless without knowing whether it was asked for in AED or SAR.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from .constants import CURRENCY_BY_COUNTRY, SITE_PATH_BY_LOCALE

# A noon SKU as it appears in URLs and payloads: N70211544V, Z08D98AD5671...
SKU_RE = re.compile(r"\b([NZ][A-Z0-9]{6,})\b")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_strings(value: Any) -> list[str]:
    """Normalise an input field into a clean list of strings.

    Accepts a list, a single string, or a newline/comma separated blob, so the
    actor behaves the same whether it is driven from the Console UI, from JSON,
    or chained from another actor.
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts: Iterable[str] = re.split(r"[\n,]+", value)
    elif isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            if isinstance(item, dict):
                # Apify's requestListSources-style entries.
                item = item.get("url") or item.get("value") or ""
            parts = [*parts, str(item)]
    else:
        parts = [str(value)]
    return [p.strip() for p in parts if p and str(p).strip()]


def locale_of(country: str, language: str) -> str:
    return f"{(language or 'en').lower()}-{(country or 'ae').lower()}"


def currency_of(country: str) -> str | None:
    return CURRENCY_BY_COUNTRY.get((country or "").lower())


def site_url(sku: str, url_slug: str | None, country: str, language: str) -> str | None:
    """Rebuild the public product URL a human would open.

    The API never returns a full URL -- only the slug in `url` -- so this is
    assembled from the slug, the SKU and the locale's site path.
    """
    path = SITE_PATH_BY_LOCALE.get(((country or "ae").lower(), (language or "en").lower()))
    if not path or not sku:
        return None
    slug = (url_slug or "p").strip("/")
    return f"https://www.noon.com/{path}/{slug}/{sku}/p/"


def parse_sku(value: str) -> str | None:
    """Pull a SKU out of whatever the user pasted.

    Accepts a bare SKU, a full noon product URL, or a URL with query junk
    attached. Returns None if nothing SKU-shaped is present, so the caller can
    emit a proper error row instead of fetching nonsense.
    """
    value = (value or "").strip()
    if not value:
        return None
    if "://" in value:
        segments = [s for s in urlparse(value).path.split("/") if s]
        # Canonical noon PDP path: /<locale>/<slug>/<SKU>/p/
        for i, seg in enumerate(segments):
            if seg == "p" and i > 0:
                candidate = segments[i - 1]
                if SKU_RE.fullmatch(candidate):
                    return candidate
        for seg in reversed(segments):
            m = SKU_RE.fullmatch(seg)
            if m:
                return m.group(1)
        return None
    if SKU_RE.fullmatch(value):
        return value
    m = SKU_RE.search(value)
    return m.group(1) if m else None


def clean_category_path(value: str) -> str:
    """Turn a category input into the API path segment.

    Accepts a bare code (`electronics-and-mobiles`), a nested code
    (`electronics-and-mobiles/mobiles-and-accessories`) or a full noon category
    URL, which carries a locale prefix the API must not receive.
    """
    value = (value or "").strip()
    if "://" in value:
        segments = [s for s in urlparse(value).path.split("/") if s]
        # Drop the locale prefix (uae-en, saudi-ar, ...) if present.
        if segments and re.fullmatch(r"[a-z]+-(en|ar)", segments[0]):
            segments = segments[1:]
        value = "/".join(segments)
    return value.strip("/")


# --- envelope -----------------------------------------------------------

def envelope(
    input_value: str,
    source: str,
    record_type: str,
    *,
    country: str,
    language: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        "country": (country or "").lower(),
        "language": (language or "").lower(),
        "locale": locale_of(country, language),
    }
    if extra:
        rec.update(extra)
    return rec


def error_record(
    input_value: str,
    error: str,
    detail: str,
    *,
    country: str = "",
    language: str = "",
    mode: str = "",
) -> dict[str, Any]:
    """A failure row carrying the same envelope and no payload.

    Emitted instead of skipping, so a consumer can tell "this input was
    processed and the entity is gone" from "the actor died halfway".
    """
    rec = envelope(input_value, "none", "ERROR", country=country, language=language)
    rec["_error"] = error
    rec["_errorDetail"] = detail
    if mode:
        rec["mode"] = mode
    return rec


# --- marketplace --------------------------------------------------------

def listing_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """The per-page context worth keeping on every product row.

    `nbHits` is passed through but is an approximate sharded counter -- the
    same query returned 1309/1293/1323/1301 on consecutive calls -- so it is
    reference only and never a stop condition.
    """
    return {
        "nbHits": payload.get("nbHits"),
        "nbPages": payload.get("nbPages"),
        "canonical_url": payload.get("canonical_url"),
        "searchEngine": payload.get("searchEngine"),
        "viewType": payload.get("viewType"),
    }


def extract_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Products from a marketplace listing page (search/category/brand)."""
    hits = payload.get("hits")
    return [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []


def product_record(
    hit: dict[str, Any],
    *,
    input_value: str,
    source: str,
    country: str,
    language: str,
    page: int,
    meta: dict[str, Any],
) -> dict[str, Any]:
    rec = envelope(
        input_value, source, "PRODUCT", country=country, language=language,
        extra={
            "currency": currency_of(country),
            "page": page,
            "productUrl": site_url(hit.get("sku"), hit.get("url"), country, language),
            **{f"listing_{k}": v for k, v in meta.items()},
        },
    )
    rec.update(hit)          # raw passthrough, last so upstream always wins
    return rec


def extract_category_tree(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the category facet into one row per category node.

    The `category` facet carries noon's whole hierarchy -- id, parent id,
    slash-joined code and children -- so a full category tree comes free with
    any listing request; there is no separate navigation endpoint (the obvious
    `/api/u/navigation/` 404s).
    """
    facet = next(
        (f for f in (payload.get("facets") or [])
         if isinstance(f, dict) and f.get("code") == "category"),
        None,
    )
    rows: list[dict[str, Any]] = []

    def walk(nodes: Any, depth: int, parent_code: str | None) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            children = node.get("children")
            rows.append({
                "id_category": node.get("id_category"),
                "id_category_parent": node.get("id_category_parent"),
                "code": node.get("code"),
                "name": node.get("name"),
                "sort_key": node.get("sort_key"),
                "depth": depth,
                "parent_code": parent_code,
                "child_count": len(children) if isinstance(children, list) else 0,
            })
            walk(children, depth + 1, node.get("code"))

    walk((facet or {}).get("data"), 0, None)
    return rows


def extract_facets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter dimensions available on a listing, minus the category tree.

    The category facet is excluded because it is enormous and has its own mode;
    what is left is the useful market-research surface -- brands with counts,
    price buckets, ratings, fulfilment flags.
    """
    out: list[dict[str, Any]] = []
    for group in ("facets", "dynamicFacets"):
        for facet in payload.get(group) or []:
            if not isinstance(facet, dict) or facet.get("code") == "category":
                continue
            data = facet.get("data")
            out.append({
                "facetGroup": group,
                "code": facet.get("code"),
                "name": facet.get("name"),
                "type": facet.get("type"),
                "optionCount": len(data) if isinstance(data, list) else 0,
                "options": data if isinstance(data, list) else None,
            })
    return out


# --- product detail & offers -------------------------------------------

def extract_offers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every competing seller offer on a product.

    This is the buy-box: one row per seller, each with its own price,
    sale_price, stock, warranty, delivery estimate and seller ratings. The
    recon SKU carried 11 of them under a single variant.
    """
    product = payload.get("product") or {}
    rows: list[dict[str, Any]] = []
    for variant in product.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for offer in variant.get("offers") or []:
            if isinstance(offer, dict):
                rows.append({
                    "variant_sku": variant.get("sku"),
                    "variant_label": variant.get("variant"),
                    **offer,
                })
    return rows


def rating_of(payload: dict[str, Any]) -> dict[str, Any] | None:
    """The aggregate rating.

    This is ALL the review data reachable: individual review bodies live in a
    service the `/_vs/nc/` allowlist does not route (see constants.py).
    """
    rating = (payload.get("product") or {}).get("product_rating")
    return rating if isinstance(rating, dict) else None


# --- noon Minutes -------------------------------------------------------

def extract_instant_products(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Products from a noon Minutes page.

    Minutes returns `hits: []` even when it has hundreds of results -- the real
    products live in CMS modules, interleaved with `adBannerSlider` entries.

    The module TYPE is not stable, so this does not key on it. The same query
    came back as `instantPLPItem` (one product under `data.product`) in one
    run and as `instantProductBox` (a `products` list) in the next, and there
    are promo module types alongside both. Keying on the type string silently
    returned zero products the day the layout changed, which is exactly the
    failure this project treats as worse than crashing. So the two known
    container shapes are read structurally, and anything product-shaped -- a
    dict carrying a `sku` -- is collected regardless of what its module is
    called.
    """
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    def take(candidate: Any) -> None:
        if isinstance(candidate, dict) and candidate.get("sku") and id(candidate) not in seen:
            seen.add(id(candidate))
            rows.append(candidate)

    for block in payload.get("results") or []:
        if not isinstance(block, dict):
            continue
        for module in block.get("modules") or []:
            if not isinstance(module, dict):
                continue
            # Shape A: a list of products on the module itself.
            for item in module.get("products") or []:
                take(item)
            # Shape B: a single product nested under `data`.
            data = module.get("data")
            if isinstance(data, dict):
                take(data.get("product"))
                for item in data.get("products") or []:
                    take(item)
    return rows
