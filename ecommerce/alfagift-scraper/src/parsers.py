"""The record envelope, input resolution, and the few derived fields.

Alfagift's JSON is clean and stable, so this module does almost no reshaping:
per this portfolio's raw-passthrough rule the upstream field names go into
`data` verbatim and downstream normalises. What it does add is the handful of
things a buyer would otherwise have to compute by hand across every row --
a canonical product URL, whether a row is actually buyable, and the real
discount in rupiah -- plus the URL parsing that lets a run be driven by pasted
alfagift.id links instead of internal ids.
"""

from __future__ import annotations

import datetime as _dt
import re
import urllib.parse
from typing import Any

from .constants import SITE_ROOT

# /p/<slug>-<productId>       productId is numeric
# /c/<slug>-<categoryId>      categoryId is a 24-char hex ObjectId
# /b/<slug>-<brandId>         brandId is numeric
# /find/<keyword-with-dashes> and the SEO twin /jual/<keyword>
# /promotion-products?id=<promotionId>   promotionId is a 24-char hex ObjectId
_PRODUCT_URL = re.compile(r"/p/(?:[^/?#]*?-)?(\d+)(?:[/?#]|$)", re.I)
_CATEGORY_URL = re.compile(r"/c/(?:[^/?#]*?-)?([0-9a-f]{24})(?:[/?#]|$)", re.I)
_BRAND_URL = re.compile(r"/b/(?:[^/?#]*?-)?(\d+)(?:[/?#]|$)", re.I)
_SEARCH_URL = re.compile(r"/(?:find|jual)/([^/?#]+)", re.I)
_OBJECT_ID = re.compile(r"^[0-9a-f]{24}$", re.I)
_NUMERIC = re.compile(r"^\d+$")


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# -- input resolution -------------------------------------------------------

def as_strings(value: Any) -> list[str]:
    """Normalise one input field into a clean list of strings.

    Accepts the three shapes the Apify console and a chaining actor produce:
    a plain list, a newline/comma-separated string, and the
    `[{"url": "..."}]` objects the `requestListSources` editor emits.
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[\n,]+", value)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(value, dict):
        value = [value]
    out: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            item = item.get("url") or item.get("value") or item.get("id") or ""
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def resolve_product_id(raw: str) -> str | None:
    """A numeric productId, or the id inside an alfagift.id /p/ URL.

    Returns None for a SKU. That distinction matters: the detail endpoint
    answers a SKU with HTTP 500 "For input string", which reads like a server
    fault rather than the caller error it is, so it is caught here instead.
    """
    raw = raw.strip()
    match = _PRODUCT_URL.search(raw)
    if match:
        return match.group(1)
    if _NUMERIC.match(raw):
        return raw
    return None


def resolve_category_id(raw: str) -> str | None:
    """A 24-hex categoryId, or the id inside an alfagift.id /c/ URL."""
    raw = raw.strip()
    match = _CATEGORY_URL.search(raw)
    if match:
        return match.group(1)
    if _OBJECT_ID.match(raw):
        return raw.lower()
    return None


def resolve_brand_id(raw: str) -> str | None:
    """A numeric brandId, or the id inside an alfagift.id /b/ URL."""
    raw = raw.strip()
    match = _BRAND_URL.search(raw)
    if match:
        return match.group(1)
    if _NUMERIC.match(raw):
        return raw
    return None


def resolve_promotion_id(raw: str) -> str | None:
    """A 24-hex promotionId, or the id inside a /promotion-products?id= URL.

    Note the trap this exists to avoid: a banner row carries BOTH its own `id`
    and, inside `bannerDeepLinkTap`, a different id that is the promotion. The
    products endpoint only accepts the second one and answers the first with a
    zero-length HTTP 200.
    """
    raw = raw.strip()
    if "?" in raw or raw.startswith("http"):
        query = urllib.parse.urlparse(raw).query
        candidate = urllib.parse.parse_qs(query).get("id", [""])[0]
        if _OBJECT_ID.match(candidate):
            return candidate.lower()
    if _OBJECT_ID.match(raw):
        return raw.lower()
    return None


def resolve_keyword(raw: str) -> str:
    """A bare keyword, or the one inside an alfagift.id /find/ or /jual/ URL.

    The site slugifies keywords into its URLs ("susu uht" -> "susu-uht"), so
    a pasted search URL has to be un-slugified before the API will match it.
    """
    raw = raw.strip()
    match = _SEARCH_URL.search(raw)
    if match:
        return urllib.parse.unquote(match.group(1)).replace("-", " ").strip()
    return raw


def promotion_id_from_banner(banner: dict[str, Any]) -> str | None:
    """Dig the promotionId out of a banner's deep link.

    Both `deepLink` (alfagift://promotion-products?id=...) and
    `bannerDeepLinkTap` (the https twin) carry it; banners that point at
    something other than a promotion carry neither, and are skipped.
    """
    for key in ("bannerDeepLinkTap", "deepLink"):
        value = banner.get(key)
        if not value:
            continue
        found = resolve_promotion_id(str(value))
        if found:
            return found
    return None


# -- derived fields ---------------------------------------------------------

def product_url(product: dict[str, Any]) -> str | None:
    """Rebuild the public /p/ URL the site would use for this product.

    Mirrors the bundle's own slug function exactly: lowercase, spaces to
    hyphens, then drop every character that is not a word character or hyphen.
    """
    product_id = product.get("productId") or product.get("id")
    name = product.get("productName") or product.get("name")
    if not product_id or not name:
        return None
    slug = re.sub(r"[^\w-]+", "", str(name).lower().replace(" ", "-"))
    return f"{SITE_ROOT}/p/{slug}-{product_id}"


def enrich_product(product: dict[str, Any]) -> dict[str, Any]:
    """Raw passthrough plus the four things every consumer recomputes anyway.

    `isBuyable` deserves a note. Alfagift keeps delisted and out-of-area
    products in every listing with `validFlag: false` and every price field set
    to 0.0, so a naive average price over a category is dragged toward zero by
    rows that are not for sale at all. The flag makes that filterable in one
    step instead of requiring the caller to know the convention.
    """
    enriched = dict(product)

    base = _as_float(product.get("basePrice"))
    final = _as_float(product.get("finalPrice"))
    valid = product.get("validFlag")

    enriched["productUrl"] = product_url(product)
    enriched["isBuyable"] = bool(valid) and final > 0
    enriched["isDiscounted"] = base > 0 and final > 0 and final < base
    enriched["discountAmount"] = round(base - final, 2) if base > final > 0 else 0.0
    return enriched


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def flatten_categories(
    nodes: list[dict[str, Any]], parent: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Walk the nested category tree into one row per node.

    Alfagift publishes only two levels here (10 level-0 parents, 51 level-1
    children) even though products carry category ids down to level 3. The
    deeper ids are real but NOT queryable -- asking the category endpoint for a
    level-2 id returns HTTP 200 with zero products -- so the tree stops here on
    purpose rather than because of a parsing gap.
    """
    rows: list[dict[str, Any]] = []
    for node in nodes or []:
        children = node.get("subCategories") or []
        row = {k: v for k, v in node.items() if k != "subCategories"}
        row["childCount"] = len(children)
        row["parentName"] = (parent or {}).get("categoryName")
        row["categoryUrl"] = _category_url(node)
        rows.append(row)
        rows.extend(flatten_categories(children, node))
    return rows


def _category_url(node: dict[str, Any]) -> str | None:
    category_id = node.get("categoryId")
    name = node.get("categoryName")
    if not category_id or not name:
        return None
    slug = re.sub(r"[^\w-]+", "", str(name).lower().replace(" ", "-"))
    return f"{SITE_ROOT}/c/{slug}-{category_id}"


def brand_url(brand: dict[str, Any]) -> str | None:
    brand_id = brand.get("id")
    name = brand.get("name")
    if not brand_id or not name:
        return None
    slug = re.sub(r"[^\w-]+", "", str(name).lower().replace(" ", "-"))
    return f"{SITE_ROOT}/b/{slug}-{brand_id}"


# -- envelope ---------------------------------------------------------------

def record(
    item_type: str,
    record_id: Any,
    data: dict[str, Any],
    *,
    mode: str,
    source_url: str | None = None,
    query: str | None = None,
    rank: int | None = None,
    page: int | None = None,
    parent_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "scrapedAt": now_iso(),
        "sourceUrl": source_url,
        "mode": mode,
    }
    if query is not None:
        meta["query"] = query
    if rank is not None:
        meta["rank"] = rank
    if page is not None:
        meta["page"] = page
    if parent_id is not None:
        meta["parentId"] = parent_id
    if extra_meta:
        meta.update(extra_meta)
    return {
        "item_type": item_type,
        "id": None if record_id is None else str(record_id),
        "data": data,
        "metadata": meta,
    }


def error_record(
    subject: str, kind: str, detail: str = "", *, mode: str = "", **meta: Any
) -> dict[str, Any]:
    """A diagnostic row.

    The run never finishes with an empty dataset: a buyer joining on this
    output reads "no rows" as a crash, while an error row says exactly which
    input failed and why.

    `id` is null here, and `.actor/output_schema.json` declares it
    ["string","null"] for that reason. Apify validates a push_data batch as a
    whole, so a single non-nullable violation discards up to 99 good rows with
    it -- see test_local.py::test_dataset_schema.
    """
    return record(
        "error",
        None,
        {"_error": kind, "_errorDetail": detail, "_input": subject},
        mode=mode,
        **meta,
    )
