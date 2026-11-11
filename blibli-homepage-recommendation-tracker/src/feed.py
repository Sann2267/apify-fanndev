"""Homepage recommendation feed extraction.

One event, one code path: for each requested tab, page through Blibli's own
`/homepage-infinite-recommendations/{tab}/products` feed and yield every
tile it places -- product recommendations, paid brand-ad banner slots, and
curated category/collection cards ("Lagi laris" / trending-now tiles) --
tagged by `_recordType` so a consumer can tell them apart. Tabs are a query
dimension (which slice of the homepage to look at), not separate events, so
this actor takes no `mode` input at all -- see CRAWLING_METHOD.md for why
that is the right call here versus `blibli-promo-extractor`'s three-mode
design.
"""

import logging
from datetime import datetime, timezone

from src.client import BlibliClient, UpstreamShapeError
from src.constants import FEED_API_TEMPLATE, TABS_API

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_ms_to_iso(value) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _absolute(url) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    return url if url.startswith("http") else "https://www.blibli.com" + url


def _effective_discount(price: dict) -> tuple:
    """`(percent, provenance)`, same defensive pattern used across this
    portfolio: Blibli's other endpoints are known to omit `price.discount`
    entirely for sub-1% reductions, so a value is always recomputed from the
    raw prices when the upstream field is missing rather than left null."""
    upstream = price.get("discount")
    if isinstance(upstream, (int, float)):
        return upstream, "upstream"
    listed, offered = price.get("listValue"), price.get("offerValue")
    if (
        isinstance(listed, (int, float))
        and isinstance(offered, (int, float))
        and listed > 0
        and offered <= listed
    ):
        return round((listed - offered) / listed * 100), "computed"
    return None, None


def _item_id(item: dict) -> str | None:
    """Stable identity for dedup: SKU for a product tile, the ad's own id
    for a banner tile, its link for a category card. All three absent is
    rare (a genuinely unrecognised tile shape) and falls back to None,
    which the caller treats as never-a-duplicate."""
    if item.get("sku"):
        return f"product:{item['sku']}"
    banner = item.get("promoBannerInfo") or {}
    if banner.get("brandAdId"):
        return f"banner:{banner['brandAdId']}"
    if item.get("url"):
        return f"card:{item['url']}"
    return None


async def fetch_tabs(client: BlibliClient) -> list[dict]:
    """Every homepage content tab Blibli currently exposes.

    Each carries a long opaque `id` and a short `name` (`TAB_1`, `TAB_5-4`).
    The feed endpoint must be called with `name` -- see CRAWLING_METHOD.md.
    """
    payload = await client.get_json(TABS_API, referer="/")
    tabs = payload.get("data")
    if not isinstance(tabs, list):
        raise UpstreamShapeError(
            f"tabs endpoint returned no `data` list (keys: {list(payload)[:10]})"
        )
    return tabs


def _record(item: dict, tab: dict, rank: int, page: int) -> dict:
    is_product = bool(item.get("sku"))
    banner = item.get("promoBannerInfo") or {}
    is_banner = bool(banner.get("brandAdId"))
    # A third tile shape sits between the two: a curated category/collection
    # card (e.g. "Sepatu Sneakers Pria" / "Lagi laris" -- trending now, X
    # sold this month) that links to a landing page rather than a single
    # product. It carries `cardLabel`/`cardDescription` and a `url` but no
    # `sku`. Caught live during Phase 3 local testing -- without this branch
    # it silently fell into "unknown", which is honest but throws away a
    # real, recurring tile type rather than describing it.
    is_card = (not is_product) and (not is_banner) and bool(item.get("cardLabel") or item.get("url"))
    record_type = "product" if is_product else (
        "ad_banner" if is_banner else ("category_card" if is_card else "unknown")
    )

    price = item.get("price") or {}
    contextual = item.get("contextualPrice") or {}
    extended = item.get("extendedData") or {}
    discount, discount_source = _effective_discount(price) if is_product else (None, None)
    list_value, offer_value = price.get("listValue"), price.get("offerValue")

    return {
        "_input": tab.get("name"),
        "_source": "S1-homepage-infinite-recommendations",
        "_scrapedAt": _now(),
        **item,
        "_tabName": tab.get("name"),
        "_tabTitle": tab.get("title"),
        "_tabSourceType": tab.get("source"),
        "_recordType": record_type,
        "_rankInFeed": rank,
        "_page": page,
        # Populated for both product tiles and category cards -- both link
        # somewhere on blibli.com; ad banners use _adRedirectUrl instead.
        "_productUrl": _absolute(item.get("url")) if (is_product or is_card) else None,
        "_cardLabel": item.get("cardLabel"),
        "_cardDescription": item.get("cardDescription"),
        "_listPrice": list_value,
        "_offerPrice": offer_value,
        "_discountPercent": discount,
        "_discountSource": discount_source,
        "_savingAmount": (
            list_value - offer_value
            if isinstance(list_value, (int, float)) and isinstance(offer_value, (int, float))
            else None
        ),
        "_contextualDiscountPercent": contextual.get("discount"),
        "_brandAdId": banner.get("brandAdId"),
        "_adBrandNames": banner.get("brandNames"),
        "_adRedirectUrl": _absolute(banner.get("redirectUrl")) if banner.get("redirectUrl") else None,
        "_adStartTime": _epoch_ms_to_iso(banner.get("startDate")),
        "_adEndTime": _epoch_ms_to_iso(banner.get("endDate")),
        "_personalizationSource": extended.get("personalizationSource"),
        "_personalizationLogic": extended.get("personalizationLogic"),
        "_strategyId": extended.get("strategyId"),
    }


async def run_feed(client: BlibliClient, tabs: list[dict], max_pages_per_tab: int,
                    max_items_per_tab: int, include_ad_banners: bool):
    """Sweep every requested tab's feed to the page cap.

    Stop conditions, in the order they can fire: `max_pages_per_tab`
    (mandatory -- this is a re-ranked/personalized feed with no reliable
    end, see constants.py), a page that adds zero new item ids (the feed
    has started repeating -- continuing wastes requests for no new data),
    an empty page, or `max_items_per_tab` emitted for this tab.
    """
    for tab in tabs:
        tab_name = tab.get("name")
        if not tab_name:
            continue
        seen: set[str] = set()
        rank = 0
        emitted = 0

        for page in range(1, max_pages_per_tab + 1):
            if max_items_per_tab and emitted >= max_items_per_tab:
                break

            payload = await client.get_json(
                FEED_API_TEMPLATE.format(tab_name=tab_name),
                params={"page": str(page)},
                referer="/",
            )
            items = payload.get("data") or []
            if not items:
                logger.info("tab=%s page=%d -> empty, stopping", tab_name, page)
                break

            new_this_page = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = _item_id(item)
                if item_id is not None:
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                new_this_page += 1
                rank += 1

                record = _record(item, tab, rank, page)
                if record["_recordType"] == "ad_banner" and not include_ad_banners:
                    continue
                yield record
                emitted += 1
                if max_items_per_tab and emitted >= max_items_per_tab:
                    break

            logger.info(
                "tab=%s page=%d -> %d item(s), %d new (%d emitted so far)",
                tab_name, page, len(items), new_this_page, emitted,
            )
            if new_this_page == 0:
                logger.info("tab=%s page=%d -> all repeats, stopping", tab_name, page)
                break
