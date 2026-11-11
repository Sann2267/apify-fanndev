"""Product sourcing, content parsing and link building."""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from src.constants import (
    IMAGE_SIZES,
    ORIGIN,
    SEARCH_API,
    SEARCH_MAX_PAGES,
    SEARCH_PAGE_SIZE,
    SHARE_LINK_API,
    SHARE_PAGE_TYPE,
    SHARE_PLATFORM,
    SORT_OPTIONS,
    WARRANTY_OFFICIAL,
)

logger = logging.getLogger(__name__)

_IMAGE_SIZE_RE = re.compile(r"/catalog/(?:%s)/" % "|".join(IMAGE_SIZES + ("large", "small")))
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InvalidInput(ValueError):
    """Input could not be used."""


# ---------------------------------------------------------------------------
# Content parsing
# ---------------------------------------------------------------------------

def parse_selling_points(raw) -> list[str]:
    """Turn Blibli's `uniqueSellingPoint` blob into clean bullet strings.

    Upstream ships a single string with literal `\\n<br>` separators and
    bullet glyphs, e.g.
    `"• Processor : Intel Core i3 \\n<br>• Memory : 8GB"`. Marketers need
    the lines, not the markup.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    text = html.unescape(raw)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    lines = []
    for chunk in text.split("\n"):
        cleaned = _WS_RE.sub(" ", chunk).strip().lstrip("•*-–").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def short_description(bullets: list[str], name: str | None, limit: int = 300) -> str | None:
    """A compact, human-readable blurb built from the selling points.

    Falls back to the product name when a listing has no selling points at
    all, so a caption is never left empty.
    """
    if not bullets:
        return name or None
    out = ""
    for bullet in bullets:
        candidate = bullet if not out else f"{out} · {bullet}"
        if len(candidate) > limit:
            break
        out = candidate
    return out or (bullets[0][:limit] if bullets else name)


def resize_image(url: str | None, size: str) -> str | None:
    """Swap the size segment inside a Blibli catalogue image URL."""
    if not isinstance(url, str) or not url:
        return None
    if size not in IMAGE_SIZES:
        return url
    return _IMAGE_SIZE_RE.sub(f"/catalog/{size}/", url)


def clean_product_url(raw: str | None) -> str | None:
    """Absolute product URL with Blibli's own tracking query stripped.

    Search results carry `?ds=&source=SEARCH&sid=&metaData=...`; those are
    session artefacts that must not end up in a shared link.
    """
    if not isinstance(raw, str) or not raw:
        return None
    path = raw.split("?")[0]
    return path if path.startswith("http") else ORIGIN + path


def build_tracked_url(product_url: str | None, campaign, source, medium) -> str | None:
    """Product URL plus UTM parameters, built locally with no API call.

    This is the link that works everywhere -- no redirect, no dependency on
    Blibli's minter staying up. Put your affiliate/creator ID in one of the
    UTM values.
    """
    if not product_url:
        return None
    params = [(k, v) for k, v in (
        ("utm_campaign", campaign), ("utm_source", source), ("utm_medium", medium)
    ) if v]
    if not params:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return product_url + sep + urlencode(params, quote_via=quote)


async def mint_share_link(client, product_url, campaign, source, medium):
    """Blibli's own OneLink short link for a product.

    Public endpoint -- no login. Returns `None` rather than raising, so a
    single minting hiccup degrades one row's `shareLink` instead of losing
    the product record entirely; `trackedUrl` is always present regardless.
    """
    if not product_url:
        return None
    body = {
        "url": product_url,
        "pageType": SHARE_PAGE_TYPE,
        "platform": SHARE_PLATFORM,
        "campaign": campaign or "share",
        "source": source or "web",
        "medium": medium or "share",
    }
    try:
        payload = await client.post_json(SHARE_LINK_API, body, referer="/")
    except Exception as exc:  # noqa: BLE001 - link minting is best-effort
        logger.warning("Share link failed for %s: %s", product_url, exc)
        return None
    return (payload.get("data") or {}).get("link")


def build_caption(record: dict, template: str | None) -> str | None:
    """Ready-to-post caption. `template` uses {placeholders}."""
    if not template:
        return None
    def _rupiah(value) -> str:
        """Indonesian thousands formatting, WITHOUT the `Rp` prefix.

        The prefix belongs to the template ("Rp{price}"), not the value --
        baking it in here produced "RpRp8.999.000" for the default template.
        """
        return f"{value:,.0f}".replace(",", ".") if isinstance(value, (int, float)) else ""

    fields = {
        "name": record.get("name") or "",
        "brand": record.get("brand") or "",
        "price": _rupiah(record.get("salePrice")),
        "listPrice": _rupiah(record.get("listPrice")),
        "discount": f"{record['discountPercent']}%" if record.get("discountPercent") else "",
        "rating": record.get("rating") or "",
        "reviewCount": record.get("reviewCount") or "",
        "sold": record.get("soldCount") or "",
        "warranty": record.get("warrantyText") or "",
        "description": record.get("shortDescription") or "",
        "link": record.get("shareLink") or record.get("trackedUrl") or "",
        "merchant": record.get("merchantName") or "",
    }
    try:
        return template.format(**fields).strip()
    except KeyError as exc:
        raise InvalidInput(
            f"captionTemplate references unknown placeholder {exc}. Available: "
            + ", ".join(sorted(fields))
        ) from exc


# ---------------------------------------------------------------------------
# Sourcing
# ---------------------------------------------------------------------------

def build_search_params(query: dict, filters: dict, page: int) -> dict:
    params = {
        "page": str(page),
        "start": str((page - 1) * SEARCH_PAGE_SIZE),
        "itemPerPage": str(SEARCH_PAGE_SIZE),
        "channelId": "web",
        "showFacet": "false",
        "sort": filters["sort"],
    }
    if query["type"] == "searchTerm":
        params["searchTerm"] = query["value"]
    else:
        params["category"] = query["value"]

    # Server-side quality gates. Pushing these to Blibli means pagination is
    # spent only on products that already qualify.
    if filters.get("min_rating"):
        # The facet only advertises 3 and 4; anything higher is enforced
        # client-side against the product's own rating.
        params["rating"] = "4" if filters["min_rating"] >= 4 else "3"
    if filters.get("official_warranty"):
        params["warrantyType"] = WARRANTY_OFFICIAL
    if filters.get("top_rated_seller"):
        params["seller"] = "Top rated seller"
    if filters.get("min_discount"):
        supported = [b for b in (10, 25, 50, 75) if b <= filters["min_discount"]]
        if supported:
            params["discount"] = str(max(supported))
    return params


def passes_filters(product: dict, filters: dict) -> bool:
    review = product.get("review") or {}
    rating = review.get("absoluteRating") or review.get("rating")
    if filters.get("min_rating") and not (
        isinstance(rating, (int, float)) and rating >= filters["min_rating"]
    ):
        return False
    if filters.get("min_reviews") and (review.get("count") or 0) < filters["min_reviews"]:
        return False
    if filters.get("min_sold") and (product.get("soldCountTotal") or 0) < filters["min_sold"]:
        return False
    if filters.get("official_store") and not product.get("officialMerchant"):
        return False
    discount = (product.get("price") or {}).get("discount")
    if filters.get("min_discount") and not (
        isinstance(discount, (int, float)) and discount >= filters["min_discount"]
    ):
        return False
    return True


def base_record(product: dict, query: dict, filters: dict, rank: int) -> dict:
    price = product.get("price") or {}
    review = product.get("review") or {}
    badge = product.get("badge") or {}
    images = [i for i in (product.get("images") or []) if isinstance(i, str)]
    bullets = parse_selling_points(product.get("uniqueSellingPoint"))
    size = filters.get("image_size", "full")
    sized = [resize_image(i, size) for i in images]
    product_url = clean_product_url(product.get("url"))

    return {
        "_input": query["label"],
        "_source": "S1-search",
        "_scrapedAt": _now(),
        **product,
        "sku": product.get("sku"),
        "name": product.get("name"),
        "brand": product.get("brand"),
        "merchantName": product.get("merchantName"),
        "merchantCode": product.get("merchantCode"),
        "isOfficialStore": product.get("officialMerchant"),
        "merchantBadge": badge.get("merchantBadge"),
        # commerce
        "salePrice": price.get("salePrice"),
        "listPrice": price.get("listPrice"),
        "discountPercent": price.get("discount"),
        "rating": review.get("absoluteRating") or review.get("rating"),
        "reviewCount": review.get("count"),
        "soldCount": product.get("soldCountTotal"),
        "categories": product.get("categoryNameHierarchy"),
        # content
        "sellingPoints": bullets,
        "shortDescription": short_description(bullets, product.get("name")),
        "primaryImage": sized[0] if sized else None,
        "images": sized,
        "imageCount": len(sized),
        # links (shareLink filled in later)
        "productUrl": product_url,
        "trackedUrl": build_tracked_url(
            product_url, filters.get("campaign"), filters.get("source"), filters.get("medium")
        ),
        "shareLink": None,
        # provenance
        "queryType": query["type"],
        "query": query["value"],
        "rankInQuery": rank,
        "officialWarrantyFilterApplied": bool(filters.get("official_warranty")),
    }


async def enrich_from_product_page(client, record: dict) -> dict:
    """Add the warranty statement and Blibli's own SEO blurb.

    Costs one request per product. The warranty object only exists on the
    product page -- search results carry `warranty: null` -- so this is the
    only way to quote the exact guarantee ("Garansi resmi 2 tahun") that an
    affiliate post wants to advertise.
    """
    url = record.get("productUrl")
    if not url:
        return record
    try:
        state = await client.get_embedded_state(url, "__PRODUCT_DETAIL_INITIAL_STATE__")
    except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
        logger.warning("Enrichment failed for %s: %s", url, exc)
        return record
    summary = (state or {}).get("productDetail.product/summary") or {}
    warranty = summary.get("warranty") or {}
    seo = summary.get("seo") or {}
    record["warrantyType"] = warranty.get("type")
    record["warrantyText"] = warranty.get("text")
    record["warrantyDuration"] = warranty.get("duration")
    record["hasOfficialWarranty"] = warranty.get("type") == "RESMI"
    record["seoDescription"] = seo.get("metaDescription")
    record["stock"] = summary.get("stock")
    return record


async def run_query(client, query, filters, max_items):
    """Yield qualifying product records for one search term or category."""
    emitted = 0
    rank = 0
    seen: set[str] = set()

    for page in range(1, SEARCH_MAX_PAGES + 1):
        if max_items and emitted >= max_items:
            return
        payload = await client.get_json(
            SEARCH_API, params=build_search_params(query, filters, page), referer="/"
        )
        data = payload.get("data") or {}
        products = [
            p for p in (data.get("products") or []) if isinstance(p, dict) and p.get("sku")
        ]
        if not products:
            return

        for product in products:
            if product["sku"] in seen:
                continue
            seen.add(product["sku"])
            rank += 1
            if not passes_filters(product, filters):
                continue
            yield base_record(product, query, filters, rank)
            emitted += 1
            if max_items and emitted >= max_items:
                return

        paging = data.get("paging") or {}
        logger.info(
            "%s=%r page=%d/%s -> %d products (%d kept)",
            query["type"], query["value"], page,
            paging.get("total_page", "?"), len(products), emitted,
        )
        if paging.get("total_page") and page >= paging["total_page"]:
            return


async def finalize(client, record, filters, semaphore):
    """Mint the share link (optional) and compose the caption."""
    if filters.get("generate_share_link"):
        async with semaphore:
            record["shareLink"] = await mint_share_link(
                client, record.get("productUrl"),
                filters.get("campaign"), filters.get("source"), filters.get("medium"),
            )
    if filters.get("enrich"):
        async with semaphore:
            record = await enrich_from_product_page(client, record)
    record["caption"] = build_caption(record, filters.get("caption_template"))
    return record
