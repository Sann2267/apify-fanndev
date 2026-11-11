"""Merchant profile assembly and catalogue enumeration."""

import logging
import re
from datetime import datetime, timezone

from src.constants import (
    CATALOG_SORTS,
    MERCHANT_FAVORITES_API,
    MERCHANT_INFO_API,
    ORIGIN,
    PRICE_BANDS,
    REVIEWS_API,
    SEARCH_API,
    SEARCH_MAX_PAGES,
    SEARCH_PAGE_SIZE,
    VOUCHERS_API,
)

logger = logging.getLogger(__name__)

_MERCHANT_URL = re.compile(r"/merchant/[^/]+/([A-Za-z0-9\-]+)")
_PRODUCT_URL = re.compile(r"/p/[^/]+/(?:ps|is)--([A-Z]{2,4}-\d{4,6})")
_MERCHANT_CODE = re.compile(r"^[A-Z]{2,4}-\d{4,6}$")


class InvalidTarget(ValueError):
    """The input string is not a recognisable Blibli store."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_ms_to_iso(value) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_store(raw: str) -> str:
    """Extract a merchant code from a store URL, product URL, or bare code.

    A product URL works too: the merchant code is the SKU's own prefix, so
    pasting any product from a competitor's store resolves to that store.
    """
    value = str(raw or "").strip()
    if not value:
        raise InvalidTarget("empty target")

    if "/" in value:
        merchant = _MERCHANT_URL.search(value)
        if merchant:
            return merchant.group(1).upper()
        product = _PRODUCT_URL.search(value)
        if product:
            return product.group(1).upper()
        raise InvalidTarget(
            f"{raw!r} is not a Blibli store URL. Expected /merchant/<name>/<CODE>."
        )

    upper = value.upper()
    # A full SKU (COP-60023-00933) carries its store code as the prefix.
    sku_prefix = re.match(r"^([A-Z]{2,4}-\d{4,6})-\d+", upper)
    if sku_prefix:
        return sku_prefix.group(1)
    if _MERCHANT_CODE.match(upper):
        return upper
    raise InvalidTarget(
        f"{raw!r} is not a recognisable Blibli store. Use a store URL, a store code "
        "like COP-60023, or any product URL/SKU from that store."
    )


class StoreNotFound(Exception):
    """The merchant code does not correspond to a real Blibli store."""


async def fetch_profile(client, code: str) -> dict:
    """The core store profile. Requires a non-chrome TLS profile (see constants).

    A code that does not exist does **not** 404. Blibli answers `200` with a
    fully-shaped but hollow profile -- every rating `0.0`, `official: false`,
    an empty `url`, and no `name` -- which would otherwise be emitted as a
    perfectly valid-looking row full of zeros. The presence of `name` is the
    discriminator.
    """
    payload = await client.get_json(
        MERCHANT_INFO_API.format(code=code), referer=f"/merchant/x/{code}"
    )
    data = payload.get("data") or {}
    if not data.get("name"):
        raise StoreNotFound(
            f"{code} is not a real Blibli store -- the profile endpoint returned a hollow "
            "record (no name, all ratings 0). Check the store code."
        )
    return data


async def fetch_followers(client, code: str):
    try:
        payload = await client.get_json(
            MERCHANT_FAVORITES_API.format(code=code), referer=f"/merchant/x/{code}"
        )
    except Exception as exc:  # noqa: BLE001 - enrichment, never fatal
        logger.warning("Follower count unavailable for %s: %s", code, exc)
        return None
    return (payload.get("data") or {}).get("totalFollowers")


async def fetch_review_summary(client, code: str) -> dict:
    """Rating histogram + Blibli's own review-topic counts for the whole store."""
    try:
        payload = await client.get_json(
            REVIEWS_API,
            params={"merchantCode": code, "page": "1", "itemPerPage": "1"},
            referer="/",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Review summary unavailable for %s: %s", code, exc)
        return {}
    return payload.get("summary") or {}


async def fetch_vouchers(client, code: str) -> list:
    try:
        payload = await client.get_json(
            VOUCHERS_API, params={"merchantCode": code}, referer=f"/merchant/x/{code}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vouchers unavailable for %s: %s", code, exc)
        return []
    return (payload.get("data") or {}).get("voucherDetails") or []


def profile_record(code, profile, followers, review_summary, vouchers, product_count):
    """One flat, analysis-ready row describing a competitor's storefront."""
    badge = profile.get("badge") or {}
    pickup = profile.get("pickupPoint") or {}
    rating = (review_summary.get("rating") or {})
    counts = rating.get("counts") or {}
    topics = (review_summary.get("filters") or {}).get("topics") or []

    def _int(value):
        return value if isinstance(value, (int, float)) else 0

    negative = _int(counts.get("1")) + _int(counts.get("2"))
    positive = _int(counts.get("4")) + _int(counts.get("5"))
    known = negative + positive + _int(counts.get("3"))

    return {
        "_input": code,
        "_source": "S1-merchant-info",
        "_scrapedAt": _now(),
        "recordType": "MERCHANT_PROFILE",
        "merchantCode": code,
        **profile,
        # --- identity -------------------------------------------------
        "merchantName": profile.get("name"),
        "storeUrl": profile.get("url") or f"{ORIGIN}/merchant/x/{code}",
        "isOfficial": profile.get("official"),
        "level": profile.get("level"),
        "activationDateIso": _epoch_ms_to_iso(profile.get("activationDate")),
        # --- seller performance, the competitor-strength signals ------
        "badgeId": badge.get("id"),
        "badgeName": badge.get("name"),
        "badgeRating": badge.get("rating"),
        "respondTimeRating": profile.get("respondTimeRating"),
        "productQualityRating": profile.get("productQualityRating"),
        "orderFulfillmentRating": profile.get("orderFullfilmentRating"),
        "fastCustomerResponseRating": badge.get("fastCustomerResponseRating"),
        "fastFulfillmentRating": badge.get("fastFulfillmentRating"),
        "orderCompletedRating": badge.get("orderCompletedRating"),
        "deliveryRating": badge.get("deliveryRating"),
        "perfectTransactionRating": badge.get("perfectTransactionRating"),
        "positiveFeedbackRating": badge.get("positiveFeedbackRating"),
        "productPerformanceRating": badge.get("productPerformanceRating"),
        "badgeCalculationDays": badge.get("calculationDays"),
        # --- shipping origin ------------------------------------------
        "province": profile.get("province"),
        "pickupPointCode": pickup.get("code"),
        "pickupPointName": pickup.get("name"),
        "pickupPointCity": pickup.get("cityName"),
        "pickupPointAddress": pickup.get("address"),
        "pickupPointLatLong": pickup.get("pickupPointLatLong"),
        "fulfilledByBlibli": pickup.get("fbbActivated"),
        "businessHours": pickup.get("businessHours"),
        # --- audience & reviews ---------------------------------------
        "totalFollowers": followers,
        "totalReviews": review_summary.get("count"),
        "reviewsWithText": review_summary.get("commentCount"),
        "averageRating": rating.get("average"),
        "ratingCounts": counts,
        "negativeSharePercent": round(negative / known * 100, 2) if known else None,
        "reviewTopicCounts": {t.get("name"): t.get("count") for t in topics if t.get("name")},
        # --- commercial footprint -------------------------------------
        "productCount": product_count,
        "voucherCount": len(vouchers),
        "vouchers": [
            {
                "name": v.get("name"),
                "code": v.get("code"),
                "title": (v.get("criteriaDetail") or {}).get("title"),
                "minCriteria": (v.get("criteriaDetail") or {}).get("minCriteria"),
                "endDateIso": _epoch_ms_to_iso(v.get("endDate")),
                "type": v.get("type"),
            }
            for v in vouchers
        ],
    }


def catalog_plan(coverage: str) -> list[dict]:
    """Query slices for the catalogue walk.

    The search backend serves at most 20 pages per query whatever the page
    size, so one slice tops out at 800 products. Most stores fit inside that
    (measured 154 and 187); large ones do not (3,112). `deep` adds sort and
    price-band slices, each opening its own window -- measured recovery on
    the 3,112-product store was 2,271 unique, versus 800 unfiltered.
    """
    plan = [{}]
    if coverage == "deep":
        plan += [{"sort": s} for s in CATALOG_SORTS]
        plan += [{"minPrice": str(lo), "maxPrice": str(hi)} for lo, hi in PRICE_BANDS]
    return plan


def product_record(product: dict, code: str, merchant_name: str | None) -> dict:
    price = product.get("price") or {}
    listed, offered = price.get("listPrice"), price.get("salePrice")
    return {
        "_input": code,
        "_source": "S2-catalog-search",
        "_scrapedAt": _now(),
        "recordType": "PRODUCT",
        **product,
        "merchantCode": code,
        "merchantName": product.get("merchantName") or merchant_name,
        "listPrice": listed,
        "salePrice": offered,
        "discountPercent": price.get("discount"),
        "productUrl": (
            product["url"] if str(product.get("url", "")).startswith("http")
            else ORIGIN + product["url"]
        ) if product.get("url") else None,
        "imageUrl": (product.get("images") or [None])[0],
        "rating": (product.get("review") or {}).get("rating"),
        "reviewCount": (product.get("review") or {}).get("count"),
        "soldCount": product.get("soldCountTotal"),
        "storeLocation": product.get("location"),
        "categories": product.get("categoryNameHierarchy"),
    }


async def fetch_catalog(client, code, coverage, max_products, merchant_name):
    """Yield deduped product records for one store."""
    seen: set[str] = set()
    emitted = 0

    for slice_ in catalog_plan(coverage):
        if max_products and emitted >= max_products:
            return
        for page in range(1, SEARCH_MAX_PAGES + 1):
            if max_products and emitted >= max_products:
                return
            params = {
                "merchant": code,
                "page": str(page),
                "start": str((page - 1) * SEARCH_PAGE_SIZE),
                "itemPerPage": str(SEARCH_PAGE_SIZE),
                "channelId": "web",
                "showFacet": "false",
                "sort": "0",
                **slice_,
            }
            payload = await client.get_json(SEARCH_API, params=params, referer="/")
            data = payload.get("data") or {}
            products = [
                p for p in (data.get("products") or []) if isinstance(p, dict) and p.get("sku")
            ]
            if not products:
                break

            new_products = [p for p in products if p["sku"] not in seen]
            for product in new_products:
                seen.add(product["sku"])
                yield product_record(product, code, merchant_name)
                emitted += 1
                if max_products and emitted >= max_products:
                    return

            logger.info(
                "catalog %s slice=%s page=%d -> %d new (%d emitted)",
                code, slice_ or "none", page, len(new_products), emitted,
            )
            paging = data.get("paging") or {}
            if paging.get("total_page") and page >= paging["total_page"]:
                break


async def count_products(client, code: str):
    """Total catalogue size as Blibli reports it -- one cheap call.

    This is the true product count, which is often larger than the number
    of products any run can actually page through (the 800-per-slice cap).
    """
    try:
        payload = await client.get_json(
            SEARCH_API,
            params={
                "merchant": code, "page": "1", "start": "0", "itemPerPage": "1",
                "channelId": "web", "showFacet": "false", "sort": "0",
            },
            referer="/",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Product count unavailable for %s: %s", code, exc)
        return None
    return ((payload.get("data") or {}).get("paging") or {}).get("total_item")
