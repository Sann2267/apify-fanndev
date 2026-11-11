"""Pure parsing: Shopify payloads -> dataset records.

Raw-passthrough rule: Shopify's own field names survive verbatim (`body_html`,
`compare_at_price`, `published_at`, ...). Only `_`-prefixed envelope keys,
`recordType`, and a few explicitly-derived convenience fields are added.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    rec = envelope(input_value, "none", "ERROR")
    rec["_error"] = error_kind
    if detail:
        rec["_errorDetail"] = detail[:1200]
    return rec


# -- money helpers ------------------------------------------------------------


def _to_float(value: object) -> float | None:
    """Shopify sends prices as decimal STRINGS ("24.00"). Never float() blindly."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def price_summary(variants: list) -> dict:
    """Min/max price, on-sale flag and stock counts across a product's variants."""
    prices, compares = [], []
    available = 0
    on_sale = False

    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        price = _to_float(variant.get("price"))
        compare = _to_float(variant.get("compare_at_price"))
        if price is not None:
            prices.append(price)
        if compare is not None:
            compares.append(compare)
        # compare_at_price only counts as a discount when it is strictly higher;
        # plenty of stores set it equal to price, which is not a sale.
        if price is not None and compare is not None and compare > price:
            on_sale = True
        if variant.get("available"):
            available += 1

    total = len([v for v in variants or [] if isinstance(v, dict)])
    return {
        "variantCount": total,
        "availableVariantCount": available,
        "inStock": available > 0,
        "minPrice": min(prices) if prices else None,
        "maxPrice": max(prices) if prices else None,
        "maxCompareAtPrice": max(compares) if compares else None,
        "onSale": on_sale,
    }


# -- records ------------------------------------------------------------------


def product_record(
    product: dict,
    input_value: str,
    source: str,
    store_domain: str,
    api_origin: str,
    record_type: str = "PRODUCT",
    extra: dict | None = None,
) -> dict:
    rec = envelope(input_value, source, record_type)
    rec["storeDomain"] = store_domain
    handle = product.get("handle")
    if handle:
        rec["productUrl"] = f"{api_origin}/products/{handle}"
    rec.update(price_summary(product.get("variants") or []))
    if extra:
        rec.update(extra)
    rec.update(product)          # raw passthrough wins
    return rec


def variant_records(
    product: dict,
    input_value: str,
    source: str,
    store_domain: str,
    api_origin: str,
) -> list[dict]:
    """One flat row per variant -- for spreadsheet users who cannot nest."""
    out = []
    handle = product.get("handle")
    for variant in product.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        rec = envelope(input_value, source, "VARIANT")
        rec["storeDomain"] = store_domain
        rec["productId"] = product.get("id")
        rec["productTitle"] = product.get("title")
        rec["productHandle"] = handle
        rec["productType"] = product.get("product_type")
        rec["vendor"] = product.get("vendor")
        rec["publishedAt"] = product.get("published_at")
        if handle:
            rec["productUrl"] = f"{api_origin}/products/{handle}"
        rec["priceValue"] = _to_float(variant.get("price"))
        rec["compareAtPriceValue"] = _to_float(variant.get("compare_at_price"))
        rec.update(variant)
        out.append(rec)
    return out


def store_record(profile, input_value: str, stats: dict | None = None) -> dict:
    """One row describing the store: identity, platform, theme, catalogue stats."""
    rec = envelope(input_value, "S1-store-profile", "STORE")
    meta = profile.meta or {}

    rec.update(
        {
            "requestedDomain": profile.requested_domain,
            "resolvedDomain": _domain(profile.resolved_origin),
            "catalogueDomain": _domain(profile.api_origin) if profile.api_origin else None,
            "myshopifyDomain": profile.myshopify_domain,
            "isShopify": profile.is_shopify,
            "detectionConfidence": profile.confidence,
            "poweredBy": profile.powered_by,
            "storefrontType": "headless" if profile.is_headless else "liquid-theme",
            "isHeadless": profile.is_headless,
            "shopifyMarkerHits": profile.marker_hits,
        }
    )

    if profile.theme:
        rec.update(profile.theme)
    else:
        rec["themeName"] = None
        rec["isThemeStoreTheme"] = None

    # Raw passthrough of the shop's own metadata, prefixed to avoid colliding
    # with our envelope/derived keys.
    for key in (
        "id",
        "name",
        "city",
        "province",
        "country",
        "currency",
        "description",
        "money_format",
        "published_products_count",
        "published_collections_count",
        "ships_to_countries",
    ):
        if key in meta:
            rec[f"shop_{key}"] = meta[key]

    if stats:
        rec.update(stats)
    if profile.notes:
        rec["_notes"] = profile.notes
    return rec


def collection_record(
    collection: dict, input_value: str, source: str, store_domain: str, api_origin: str
) -> dict:
    rec = envelope(input_value, source, "COLLECTION")
    rec["storeDomain"] = store_domain
    handle = collection.get("handle")
    if handle:
        rec["collectionUrl"] = f"{api_origin}/collections/{handle}"
    rec.update(collection)
    return rec


def change_record(
    input_value: str,
    store_domain: str,
    change_type: str,
    product: dict | None,
    detail: dict,
) -> dict:
    """A diff row: NEW / REMOVED / PRICE_CHANGED / BACK_IN_STOCK / OUT_OF_STOCK."""
    rec = envelope(input_value, "S1-snapshot-diff", "CHANGE")
    rec["storeDomain"] = store_domain
    rec["changeType"] = change_type
    rec.update(detail)
    if product:
        rec["title"] = product.get("title")
        rec["handle"] = product.get("handle")
        rec["productId"] = product.get("id")
        rec["vendor"] = product.get("vendor")
        rec["product_type"] = product.get("product_type")
        rec["published_at"] = product.get("published_at")
    return rec


def _domain(origin: str | None) -> str | None:
    if not origin:
        return None
    return origin.split("://", 1)[-1].split("/", 1)[0]


def snapshot_entry(product: dict) -> dict:
    """The minimal fingerprint stored between runs for change detection."""
    summary = price_summary(product.get("variants") or [])
    return {
        "t": product.get("title"),
        "h": product.get("handle"),
        "p": summary["minPrice"],
        "c": summary["maxCompareAtPrice"],
        "a": summary["inStock"],
        "v": summary["variantCount"],
        "pub": product.get("published_at"),
    }
