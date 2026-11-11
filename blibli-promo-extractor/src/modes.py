"""The three extraction modes.

Each mode is an async generator yielding dataset-ready records that already
carry the portfolio envelope (`_input`, `_source`, `_scrapedAt`). Upstream
field names are passed through verbatim per the raw-passthrough convention;
the only added fields are the envelope plus a small number of explicitly
namespaced conveniences (`_discountPercent`, `_scheduleId`, ...) that a
price-comparison consumer would otherwise have to recompute on every row.
"""

import logging
from datetime import datetime, timezone

from src.client import BlibliClient, UpstreamShapeError
from src.constants import (
    FLASH_SALE_MAX_PAGES,
    FLASH_SALE_PRODUCTS_API,
    FLASH_SALE_SCHEDULES_API,
    FLASH_SALE_SORTS,
    ORIGIN,
    PROMOTIONS_API,
    PROMOTIONS_PAGE_SIZE,
    SEARCH_API,
    SEARCH_MAX_PAGES,
    SEARCH_PAGE_SIZE,
    SEARCH_SORTS,
)

logger = logging.getLogger(__name__)

# The only values Blibli's `discount` facet advertises. The parameter means
# "at least this percent off", so an arbitrary user threshold is snapped
# down to the nearest bucket and the exact figure enforced client-side.
DISCOUNT_BUCKETS = (10, 25, 50, 75)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(source: str, input_value: str) -> dict:
    return {"_input": input_value, "_source": source, "_scrapedAt": _now()}


def _epoch_ms_to_iso(value) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _absolute(url) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    return url if url.startswith("http") else ORIGIN + url


def _effective_discount(price: dict, list_key: str, offer_key: str) -> tuple:
    """Return `(percent, provenance)` for a product's headline discount.

    Blibli omits `price.discount` entirely whenever the reduction rounds to
    under 1% (e.g. 8,999,000 -> 8,989,000). That left roughly half the rows
    of a full flash sale run with a null discount even though both prices
    were present, so the figure is recomputed from the prices in that case
    and the source recorded, rather than reporting a hole.
    """
    upstream = price.get("discount")
    if isinstance(upstream, (int, float)):
        return upstream, "upstream"
    listed, offered = price.get(list_key), price.get(offer_key)
    if (
        isinstance(listed, (int, float))
        and isinstance(offered, (int, float))
        and listed > 0
        and offered <= listed
    ):
        return round((listed - offered) / listed * 100), "computed"
    return None, None


def _meets_discount(discount, min_discount: int | None) -> bool:
    if not min_discount:
        return True
    return isinstance(discount, (int, float)) and discount >= min_discount


# ---------------------------------------------------------------------------
# Mode 1: flash sale
# ---------------------------------------------------------------------------

async def fetch_schedules(client: BlibliClient) -> list[dict]:
    """Current + upcoming flash sale session windows."""
    payload = await client.get_json(FLASH_SALE_SCHEDULES_API, referer="/flashsale")
    data = payload.get("data") or {}
    schedules = data.get("schedules")
    if not isinstance(schedules, list):
        raise UpstreamShapeError(
            "flashsale schedules endpoint returned no `schedules` list "
            f"(data keys: {list(data)[:10]})"
        )
    return schedules


def _flash_sale_record(product: dict, schedule: dict, category: str | None) -> dict:
    flash = product.get("flashsale") or {}
    quota = flash.get("quota") or {}
    price = product.get("price") or {}
    list_value, offer_value = price.get("listValue"), price.get("offerValue")
    discount, discount_source = _effective_discount(price, "listValue", "offerValue")
    return {
        **_envelope("S1-flashsale-v2", schedule.get("id", "")),
        **product,
        # Namespaced conveniences -- the headline numbers a discount analyst
        # filters on, lifted out of their nested containers.
        "_discountPercent": discount,
        "_discountSource": discount_source,
        "_listPrice": list_value,
        "_offerPrice": offer_value,
        "_savingAmount": (
            list_value - offer_value
            if isinstance(list_value, (int, float)) and isinstance(offer_value, (int, float))
            else None
        ),
        # `quota.percentage` is how much of the flash-sale allocation is
        # already gone -- the closest public proxy for sell-through speed.
        "_quotaClaimedPercent": quota.get("percentage"),
        "_quotaStatus": quota.get("status"),
        # Price after stacking payment/voucher promos -- see the same field
        # in `_discounted_record`.
        "_contextualDiscountPercent": (product.get("contextualPrice") or {}).get("discount"),
        "_campaignCode": flash.get("campaignCode"),
        "_isExclusive": flash.get("exclusive"),
        "_scheduleId": schedule.get("id"),
        "_scheduleStart": _epoch_ms_to_iso(schedule.get("start")),
        "_scheduleEnd": _epoch_ms_to_iso(schedule.get("end")),
        "_categoryFilter": category,
        "_productUrl": _absolute(product.get("url")),
        "_merchantUrl": _absolute(product.get("merchantUrl")),
    }


async def run_flash_sale(client, schedules, categories, sort, min_discount, max_items):
    """Walk every requested schedule (optionally per category) to exhaustion.

    Stops on the first empty page, on a page that adds no new SKU, or at
    `max_items` -- whichever comes first. The endpoint carries no paging
    metadata, so an empty page is the authoritative end-of-list signal
    (observed live: 768 unique products over 32 pages, empty at page 33).
    """
    sort_value = FLASH_SALE_SORTS.get(sort)
    emitted = 0
    seen: set[str] = set()

    for schedule in schedules:
        schedule_id = schedule.get("id")
        if not schedule_id:
            continue
        for category in categories or [None]:
            page = 1
            while page <= FLASH_SALE_MAX_PAGES:
                if max_items and emitted >= max_items:
                    return
                params = {"schedule_id": schedule_id, "page": str(page)}
                if sort_value:
                    params["sort"] = sort_value
                if category:
                    params["c1Category"] = category

                payload = await client.get_json(
                    FLASH_SALE_PRODUCTS_API, params=params, referer="/flashsale"
                )
                items = payload.get("data") or []
                # Non-product tiles (banners, digital top-up entries) share
                # the list; a missing `sku` is the discriminator.
                products = [p for p in items if isinstance(p, dict) and p.get("sku")]
                if not products:
                    break

                new_products = [p for p in products if p["sku"] not in seen]
                if not new_products:
                    break

                for product in new_products:
                    seen.add(product["sku"])
                    record = _flash_sale_record(product, schedule, category)
                    if not _meets_discount(record["_discountPercent"], min_discount):
                        continue
                    yield record
                    emitted += 1
                    if max_items and emitted >= max_items:
                        return

                logger.info(
                    "flashSale schedule=%s category=%s page=%d -> %d new (%d emitted)",
                    schedule_id, category or "all", page, len(new_products), emitted,
                )
                page += 1


# ---------------------------------------------------------------------------
# Mode 2: promo campaign catalogue
# ---------------------------------------------------------------------------

async def run_promo_campaigns(client, sort, max_items):
    """Every published promo campaign, paged via the endpoint's own metadata."""
    emitted = 0
    page = 1
    total_page = None

    while True:
        if max_items and emitted >= max_items:
            return
        payload = await client.get_json(
            PROMOTIONS_API,
            params={"page": str(page), "itemPerPage": str(PROMOTIONS_PAGE_SIZE), "sort": sort},
            referer="/promosi",
        )
        items = payload.get("data") or []
        if not items:
            return
        paging = payload.get("paging") or {}
        total_page = paging.get("total_page", total_page)

        for promo in items:
            if not isinstance(promo, dict):
                continue
            yield {
                **_envelope("S2-promotions", sort),
                **promo,
                "_startTime": _epoch_ms_to_iso(promo.get("startTime")),
                "_endTime": _epoch_ms_to_iso(promo.get("endTime")),
                "_promoUrl": _absolute(promo.get("url")),
            }
            emitted += 1
            if max_items and emitted >= max_items:
                return

        logger.info(
            "promoCampaigns page=%d/%s -> %d items (%d emitted)",
            page, total_page or "?", len(items), emitted,
        )
        page += 1
        if total_page and page > total_page:
            return


# ---------------------------------------------------------------------------
# Mode 3: discounted / promo-tagged products
# ---------------------------------------------------------------------------

def _discounted_record(product: dict, query: dict, rank: int) -> dict:
    price = product.get("price") or {}
    campaign = product.get("campaignInfo") or {}
    # The search backend names its price fields differently from the flash
    # sale backend: `listPrice`/`salePrice` here vs `listValue`/`offerValue`
    # there. Confirmed live -- assuming one shape for both silently nulls
    # every price in this mode.
    listed, offered = price.get("listPrice"), price.get("salePrice")
    discount, discount_source = _effective_discount(price, "listPrice", "salePrice")
    return {
        **_envelope("S3-search-discount", query["label"]),
        **product,
        "_discountPercent": discount,
        "_discountSource": discount_source,
        "_listPrice": listed,
        "_offerPrice": offered,
        "_savingAmount": (
            listed - offered
            if isinstance(listed, (int, float)) and isinstance(offered, (int, float))
            else None
        ),
        # `contextualPrice` is the price after stacking payment-method and
        # voucher promos on top -- normally a few points deeper than the
        # headline discount, and the better measure of true aggressiveness.
        "_contextualDiscountPercent": (product.get("contextualPrice") or {}).get("discount"),
        "_campaignCode": campaign.get("code") or product.get("campaignCodeWithoutSession"),
        "_campaignName": campaign.get("name"),
        "_promoEndTime": _epoch_ms_to_iso(product.get("promoEndTime")),
        "_queryType": query["type"],
        "_query": query["value"],
        "_rankInQuery": rank,
        "_minDiscountFilter": query.get("minDiscount"),
        "_promoFilter": query.get("promoFilter"),
        "_productUrl": _absolute(product.get("url")),
    }


async def run_discounted_products(client, queries, min_discount, promo_filter, sort, max_items):
    """Search-API sweep with Blibli's own `discount` / `promo` facets applied.

    The search backend refuses to serve past page 20 whatever the page size,
    so a single query tops out at 800 products; narrow by category or add
    more search terms to go wider.
    """
    sort_value = SEARCH_SORTS.get(sort, "0")
    bucket = None
    if min_discount:
        supported = [b for b in DISCOUNT_BUCKETS if b <= min_discount]
        bucket = str(max(supported)) if supported else None

    for query in queries:
        emitted_for_query = 0
        rank = 0
        for page in range(1, SEARCH_MAX_PAGES + 1):
            if max_items and emitted_for_query >= max_items:
                break
            params = {
                "page": str(page),
                "start": str((page - 1) * SEARCH_PAGE_SIZE),
                "itemPerPage": str(SEARCH_PAGE_SIZE),
                "channelId": "web",
                "showFacet": "false",
                "sort": sort_value,
            }
            if query["type"] == "searchTerm":
                params["searchTerm"] = query["value"]
            else:
                params["category"] = query["value"]
            if bucket:
                params["discount"] = bucket
            if promo_filter:
                params["promo"] = promo_filter

            payload = await client.get_json(SEARCH_API, params=params, referer="/")
            data = payload.get("data") or {}
            products = data.get("products") or []
            if not products:
                break

            enriched = {**query, "minDiscount": min_discount, "promoFilter": promo_filter}
            for product in products:
                if not isinstance(product, dict):
                    continue
                rank += 1
                record = _discounted_record(product, enriched, rank)
                if not _meets_discount(record["_discountPercent"], min_discount):
                    continue
                yield record
                emitted_for_query += 1
                if max_items and emitted_for_query >= max_items:
                    break

            paging = data.get("paging") or {}
            logger.info(
                "discountedProducts %s=%r page=%d/%s -> %d products (%d kept)",
                query["type"], query["value"], page,
                paging.get("total_page", "?"), len(products), emitted_for_query,
            )
            if paging.get("total_page") and page >= paging["total_page"]:
                break
