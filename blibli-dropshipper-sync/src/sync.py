"""SKU resolution, bulk fetch, page fallback, and change detection."""

import logging
import re
from datetime import datetime, timezone

from src.constants import (
    BASIC_API,
    BATCH_SIZE,
    CHANGE_BACK_IN_STOCK,
    CHANGE_NAME_CHANGED,
    CHANGE_NEW,
    CHANGE_OUT_OF_STOCK,
    CHANGE_PRICE_DOWN,
    CHANGE_PRICE_UP,
    CHANGE_RESTORED,
    CHANGE_UNAVAILABLE,
    CHANGE_UNCHANGED,
    ORIGIN,
    PRODUCT_PAGE,
    PRODUCT_STATE_VAR,
    PRODUCT_SUMMARY_KEY,
    SYNC_NOT_FOUND,
    SYNC_OK,
)

logger = logging.getLogger(__name__)

_PRODUCT_URL = re.compile(r"/p/[^/]+/(?:ps|is)--([A-Z]{2,4}-\d{4,6}-\d{3,6})", re.I)
_SKU = re.compile(r"^[A-Z]{2,4}-\d{4,6}-\d{3,6}$")
_TAG_RE = re.compile(r"<[^>]+>")


class InvalidInput(ValueError):
    """The input could not be resolved to a Blibli product SKU."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_sku(raw: str) -> str:
    """Accept a product URL or a bare product SKU and return the SKU."""
    value = str(raw or "").strip()
    if not value:
        raise InvalidInput("empty entry")
    if "/" in value:
        match = _PRODUCT_URL.search(value)
        if match:
            return match.group(1).upper()
        raise InvalidInput(
            f"{raw!r} is not a Blibli product URL. Expected /p/<name>/ps--<SKU>."
        )
    upper = value.upper()
    if _SKU.match(upper):
        return upper
    raise InvalidInput(
        f"{raw!r} is not a Blibli product SKU. Expected a form like COP-60023-00933, "
        "or a full product URL."
    )


def chunked(items: list, size: int = BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def clean_text(raw) -> str | None:
    """Strip Blibli's `\\n<br>` markup out of a description blob."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip().lstrip("•*-–").strip()
             for ln in text.split("\n")]
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned or None


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

async def fetch_bulk(client, skus: list[str]) -> dict:
    """Resolve a batch of SKUs in one request. Returns {sku: record}."""
    payload = await client.get_json(BASIC_API, params={"sku": ",".join(skus)}, referer="/")
    out = {}
    for item in payload.get("data") or []:
        if isinstance(item, dict) and item.get("productSku"):
            out[item["productSku"].upper()] = item
    return out


async def fetch_page(client, sku: str) -> dict | None:
    """Product-page summary for one SKU.

    The slug segment of the URL is ignored by Blibli, so the SKU alone is
    enough. Returns `None` when the page carries no product state, which is
    the only reliable "this product does not exist" signal.
    """
    state = await client.get_embedded_state(
        PRODUCT_PAGE.format(sku=sku), PRODUCT_STATE_VAR
    )
    if not state:
        return None
    return state.get(PRODUCT_SUMMARY_KEY) or None


# ---------------------------------------------------------------------------
# Record shaping
# ---------------------------------------------------------------------------

def record_from_bulk(sku: str, item: dict) -> dict:
    price = item.get("price") or {}
    review = item.get("review") or {}
    offered = price.get("offered")
    listed = price.get("listed")
    return {
        "_input": sku,
        "_source": "S1-bulk",
        "_scrapedAt": _now(),
        "sku": sku,
        "syncStatus": SYNC_OK,
        "name": item.get("name"),
        "brand": item.get("brand"),
        "merchantCode": item.get("merchantCode"),
        "merchantName": item.get("merchantName"),
        "price": offered,
        "listPrice": listed,
        "salePrice": price.get("salePrice"),
        "discountPercent": price.get("discount"),
        "currency": "IDR",
        # `_basic` exposes availability as a boolean only; exact quantity
        # needs the product page (detailed mode).
        "inStock": bool(item.get("stock")),
        "stockQuantity": None,
        "rating": review.get("rating"),
        "reviewCount": review.get("count"),
        "imageUrl": item.get("image"),
        "productUrl": (item.get("url") or "").split("?")[0] or None,
        "hasVariants": item.get("hasVariants"),
        "description": None,
        "warrantyText": None,
        "categories": None,
    }


def record_from_page(sku: str, summary: dict) -> dict:
    price = summary.get("price") or {}
    review = summary.get("review") or {}
    merchant = summary.get("merchant") or {}
    warranty = summary.get("warranty") or {}
    stock = summary.get("stock")
    images = [i.get("full") or i.get("thumbnail") for i in (summary.get("images") or [])
              if isinstance(i, dict)]
    if not images:
        images = [i for i in (summary.get("images") or []) if isinstance(i, str)]
    return {
        "_input": sku,
        "_source": "S2-product-page",
        "_scrapedAt": _now(),
        "sku": sku,
        "syncStatus": SYNC_OK,
        "name": summary.get("name"),
        "brand": (summary.get("brand") or {}).get("name"),
        "merchantCode": merchant.get("code"),
        "merchantName": merchant.get("name"),
        "price": price.get("offered"),
        "listPrice": price.get("listed"),
        "salePrice": price.get("offered"),
        "discountPercent": price.get("totalDiscount") or price.get("listDiscount"),
        "currency": "IDR",
        "inStock": bool(stock) if isinstance(stock, (int, float)) else None,
        "stockQuantity": stock if isinstance(stock, (int, float)) else None,
        "stockLimitedThreshold": summary.get("stockLimitedThreshold"),
        "rating": review.get("decimalRating") or review.get("rating"),
        "reviewCount": review.get("count"),
        "imageUrl": images[0] if images else None,
        "images": images,
        "productUrl": (summary.get("url") or "").split("?")[0] or None,
        "description": clean_text(summary.get("uniqueSellingPoint")),
        "warrantyText": warranty.get("text"),
        "warrantyType": warranty.get("type"),
        "isPreOrder": (summary.get("preOrder") or {}).get("isPreOrder"),
        "categories": [c.get("name") for c in (summary.get("categories") or [])
                       if isinstance(c, dict) and c.get("name")],
        "hasVariants": bool(summary.get("options")),
    }


def not_found_record(sku: str) -> dict:
    return {
        "_input": sku,
        "_source": "none",
        "_scrapedAt": _now(),
        "sku": sku,
        "syncStatus": SYNC_NOT_FOUND,
        "inStock": False,
        "_error": SYNC_NOT_FOUND,
        "_errorDetail": (
            f"{sku} returned no data from the bulk endpoint and its product page carries "
            "no product state. The listing appears to be removed -- consider unpublishing "
            "it from your own store."
        ),
    }


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def snapshot_entry(record: dict) -> dict:
    """The minimal state worth carrying between runs."""
    return {
        "price": record.get("price"),
        "inStock": record.get("inStock"),
        "stockQuantity": record.get("stockQuantity"),
        "name": record.get("name"),
        "syncStatus": record.get("syncStatus"),
    }


def detect_changes(record: dict, previous: dict | None) -> dict:
    """Classify what moved since the last run.

    Returns the record with `changeType`, `changes` and `hasChanged` filled
    in. A dropshipper syncs on `hasChanged` and reads `changes` to know
    exactly which fields to push.
    """
    if previous is None:
        record["changeType"] = [CHANGE_NEW]
        record["changes"] = {}
        record["hasChanged"] = True
        return record

    changes: dict = {}
    types: list[str] = []

    old_status = previous.get("syncStatus")
    new_status = record.get("syncStatus")
    if old_status == SYNC_OK and new_status == SYNC_NOT_FOUND:
        types.append(CHANGE_UNAVAILABLE)
    elif old_status == SYNC_NOT_FOUND and new_status == SYNC_OK:
        types.append(CHANGE_RESTORED)

    old_price, new_price = previous.get("price"), record.get("price")
    if isinstance(old_price, (int, float)) and isinstance(new_price, (int, float)):
        if new_price > old_price:
            types.append(CHANGE_PRICE_UP)
        elif new_price < old_price:
            types.append(CHANGE_PRICE_DOWN)
        if new_price != old_price:
            changes["price"] = {
                "from": old_price, "to": new_price,
                "deltaPercent": round((new_price - old_price) / old_price * 100, 2)
                if old_price else None,
            }

    old_stock, new_stock = previous.get("inStock"), record.get("inStock")
    if isinstance(old_stock, bool) and isinstance(new_stock, bool) and old_stock != new_stock:
        types.append(CHANGE_BACK_IN_STOCK if new_stock else CHANGE_OUT_OF_STOCK)
        changes["inStock"] = {"from": old_stock, "to": new_stock}

    old_qty, new_qty = previous.get("stockQuantity"), record.get("stockQuantity")
    if (
        isinstance(old_qty, (int, float)) and isinstance(new_qty, (int, float))
        and old_qty != new_qty
    ):
        changes["stockQuantity"] = {"from": old_qty, "to": new_qty}

    old_name, new_name = previous.get("name"), record.get("name")
    if old_name and new_name and old_name != new_name:
        types.append(CHANGE_NAME_CHANGED)
        changes["name"] = {"from": old_name, "to": new_name}

    record["changeType"] = types or [CHANGE_UNCHANGED]
    record["changes"] = changes
    record["hasChanged"] = bool(types and types != [CHANGE_UNCHANGED]) or bool(changes)
    return record


async def sync_skus(client, skus, detailed, verify_missing):
    """Resolve every SKU, yielding one record each.

    Fast path is the bulk endpoint. Any SKU it omits is re-checked against
    its product page before being called missing -- the bulk endpoint drops
    some live products (see constants), and reporting those as delisted
    would push a reseller to unpublish sellable stock.
    """
    for batch in chunked(list(skus)):
        found: dict = {}
        if not detailed:
            found = await fetch_bulk(client, batch)
            for sku, item in found.items():
                yield record_from_bulk(sku, item)

        missing = [s for s in batch if s not in found]
        for sku in missing:
            if not detailed and not verify_missing:
                # Explicitly opted out of verification: report as missing but
                # say so, rather than implying it was confirmed.
                record = not_found_record(sku)
                record["_errorDetail"] = (
                    f"{sku} was not returned by the bulk endpoint. Product-page "
                    "verification is disabled, so this has NOT been confirmed -- the "
                    "bulk endpoint is known to omit some live products."
                )
                yield record
                continue
            summary = await fetch_page(client, sku)
            if summary:
                if not detailed:
                    logger.info("%s missing from bulk but live on its page", sku)
                yield record_from_page(sku, summary)
            else:
                yield not_found_record(sku)
