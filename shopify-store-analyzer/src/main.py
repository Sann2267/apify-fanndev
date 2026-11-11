"""Shopify Store Analyzer -- one URL in, store profile + catalogue + changes out.

Modes:
  store-analysis  (default) store identity, theme, catalogue stats + newest products
  products                  the full catalogue with variants and prices
  new-products              only products published since a cutoff
  changes                   diff against the previous run's snapshot
  collections               the collection catalogue
  detect                    cheap "is this Shopify, which theme" with no crawl
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apify import Actor

from .client import HttpError, NotJson, ShopifyClient, UnexpectedShape
from .constants import (
    COLLECTIONS_PAGE_SIZE,
    MAX_PAGES,
    PATH_COLLECTIONS,
    PATH_PRODUCTS,
    PRODUCTS_PAGE_SIZE,
    SNAPSHOT_STORE_NAME,
)
from .extractor import (
    change_record,
    collection_record,
    error_record,
    price_summary,
    product_record,
    snapshot_entry,
    store_record,
    variant_records,
)
from .resolver import (
    DomainUnreachable,
    InvalidStoreUrl,
    NoCatalogueApi,
    NotShopify,
    StoreProfile,
    resolve_store,
)
from .input_errors import input_error

log = logging.getLogger("shopify")

MODES = {
    "store-analysis",
    "products",
    "new-products",
    "changes",
    "collections",
    "detect",
}

RECOVERABLE = (
    HttpError,
    NotJson,
    NotShopify,
    NoCatalogueApi,
    DomainUnreachable,
    InvalidStoreUrl,
    asyncio.TimeoutError,
)


class RunCounters:
    def __init__(self) -> None:
        self.pushed = 0
        self.errors = 0
        self.stores_ok = 0


async def push(record: dict, counters: RunCounters) -> None:
    await Actor.push_data(record)
    counters.pushed += 1
    if record.get("_error"):
        counters.errors += 1


# -- catalogue paging ---------------------------------------------------------


async def iter_products(
    client: ShopifyClient,
    api_origin: str,
    max_products: int | None = None,
    published_after: datetime | None = None,
):
    """Yield products page by page.

    /products.json is strictly published_at DESCENDING (verified over 7,443
    products across 5 stores, zero out-of-order pairs). That contract is what
    lets `published_after` stop early instead of crawling the whole catalogue --
    once a page's last item is older than the cutoff, everything after it is too.

    Note `sort_by`, `order` and `since_id` are silently ignored by Shopify here,
    so paging is strictly `page=1..N` and we never pass them.
    """
    collected = 0
    for page in range(1, MAX_PAGES + 1):
        url = f"{api_origin}{PATH_PRODUCTS}?limit={PRODUCTS_PAGE_SIZE}&page={page}"
        payload = await client.get_json(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            raise UnexpectedShape(
                f"{url} did not return a products array; got "
                f"{sorted(payload)[:8] if isinstance(payload, dict) else type(payload).__name__}"
            )
        products = payload["products"]
        if not products:
            return

        stop = False
        for product in products:
            if not isinstance(product, dict):
                raise UnexpectedShape("products[] entry is not an object.")
            if published_after is not None:
                published = _parse_dt(product.get("published_at"))
                if published is not None and published < published_after:
                    stop = True
                    break
            yield product
            collected += 1
            if max_products is not None and collected >= max_products:
                return
        if stop:
            return
        if len(products) < PRODUCTS_PAGE_SIZE:
            return


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def collect_products(
    client: ShopifyClient,
    profile: StoreProfile,
    max_products: int | None,
    published_after: datetime | None = None,
) -> list[dict]:
    out = []
    async for product in iter_products(
        client, profile.api_origin, max_products, published_after
    ):
        out.append(product)
    return out


def catalogue_stats(products: list[dict]) -> dict:
    """Aggregate figures for the STORE row -- what an analyst wants at a glance."""
    if not products:
        return {"productsScraped": 0}

    prices, vendors, types, tags = [], set(), set(), set()
    variants = on_sale = in_stock = 0
    newest = oldest = None

    for product in products:
        summary = price_summary(product.get("variants") or [])
        if summary["minPrice"] is not None:
            prices.append(summary["minPrice"])
        variants += summary["variantCount"]
        on_sale += 1 if summary["onSale"] else 0
        in_stock += 1 if summary["inStock"] else 0
        if product.get("vendor"):
            vendors.add(product["vendor"])
        if product.get("product_type"):
            types.add(product["product_type"])
        for tag in product.get("tags") or []:
            tags.add(tag)
        published = product.get("published_at")
        if isinstance(published, str) and published:
            newest = published if newest is None or published > newest else newest
            oldest = published if oldest is None or published < oldest else oldest

    return {
        "productsScraped": len(products),
        "variantCount": variants,
        "vendorCount": len(vendors),
        "productTypeCount": len(types),
        "distinctTagCount": len(tags),
        "productsOnSale": on_sale,
        "productsInStock": in_stock,
        "productsOutOfStock": len(products) - in_stock,
        "minPrice": min(prices) if prices else None,
        "maxPrice": max(prices) if prices else None,
        "avgPrice": round(sum(prices) / len(prices), 2) if prices else None,
        "newestPublishedAt": newest,
        "oldestPublishedAt": oldest,
    }


# -- modes --------------------------------------------------------------------


async def run_detect(client, profile: StoreProfile, raw: str, counters: RunCounters) -> None:
    await push(store_record(profile, raw), counters)


async def run_store_analysis(
    client, profile: StoreProfile, raw: str, counters: RunCounters, opts: dict
) -> None:
    """The flagship: one URL -> who they are, what theme, and what is new."""
    newest_n = opts["newestProducts"]
    # Cap the crawl for the stats: a full 250k-product catalogue is not worth
    # pulling just to describe a store. maxProducts governs it.
    products = await collect_products(client, profile, opts["maxProducts"])
    stats = catalogue_stats(products)
    stats["shopifyReportedProductCount"] = (profile.meta or {}).get(
        "published_products_count"
    )
    await push(store_record(profile, raw, stats), counters)

    domain = profile.requested_domain
    for product in products[:newest_n]:
        await push(
            product_record(
                product, raw, "S1-products-json", domain, profile.api_origin, "NEW_PRODUCT"
            ),
            counters,
        )


async def run_products(
    client, profile: StoreProfile, raw: str, counters: RunCounters, opts: dict
) -> None:
    domain = profile.requested_domain
    count = 0
    async for product in iter_products(client, profile.api_origin, opts["maxProducts"]):
        await push(
            product_record(product, raw, "S1-products-json", domain, profile.api_origin),
            counters,
        )
        if opts["explodeVariants"]:
            for rec in variant_records(
                product, raw, "S1-products-json", domain, profile.api_origin
            ):
                await push(rec, counters)
        count += 1
    if count == 0:
        await push(error_record(raw, "empty_catalogue", "Store published 0 products."), counters)


async def run_new_products(
    client, profile: StoreProfile, raw: str, counters: RunCounters, opts: dict
) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=opts["newWithinDays"])
    domain = profile.requested_domain
    count = 0
    async for product in iter_products(
        client, profile.api_origin, opts["maxProducts"], published_after=cutoff
    ):
        await push(
            product_record(
                product, raw, "S1-products-json", domain, profile.api_origin, "NEW_PRODUCT",
                extra={"newWithinDays": opts["newWithinDays"]},
            ),
            counters,
        )
        count += 1
    if count == 0:
        await push(
            error_record(
                raw,
                "no_new_products",
                f"No products published in the last {opts['newWithinDays']} day(s).",
            ),
            counters,
        )


async def run_collections(
    client, profile: StoreProfile, raw: str, counters: RunCounters, opts: dict
) -> None:
    domain = profile.requested_domain
    total = 0
    for page in range(1, MAX_PAGES + 1):
        url = f"{profile.api_origin}{PATH_COLLECTIONS}?limit={COLLECTIONS_PAGE_SIZE}&page={page}"
        payload = await client.get_json(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("collections"), list):
            raise UnexpectedShape(f"{url} did not return a collections array.")
        collections = payload["collections"]
        if not collections:
            break
        for collection in collections:
            if isinstance(collection, dict):
                await push(
                    collection_record(
                        collection, raw, "S1-collections-json", domain, profile.api_origin
                    ),
                    counters,
                )
                total += 1
        if len(collections) < COLLECTIONS_PAGE_SIZE:
            break
    if total == 0:
        await push(error_record(raw, "no_collections", "Store published 0 collections."), counters)


async def run_changes(
    client, profile: StoreProfile, raw: str, counters: RunCounters, opts: dict
) -> None:
    """Diff this run's catalogue against the previous run's stored snapshot.

    First run for a store has nothing to diff against, so it stores the baseline
    and says so explicitly rather than emitting a misleading "everything is new".
    """
    store = await Actor.open_key_value_store(name=SNAPSHOT_STORE_NAME)
    key = "snap_" + "".join(
        ch if ch.isalnum() else "_" for ch in (profile.myshopify_domain or profile.requested_domain)
    )

    products = await collect_products(client, profile, opts["maxProducts"])
    current = {str(p["id"]): snapshot_entry(p) for p in products if p.get("id") is not None}
    by_id = {str(p["id"]): p for p in products if p.get("id") is not None}

    previous = await store.get_value(key)
    domain = profile.requested_domain

    if not isinstance(previous, dict) or not previous.get("items"):
        await store.set_value(key, {"capturedAt": _now_iso(), "items": current})
        await push(
            {
                **store_record(profile, raw, catalogue_stats(products)),
                "recordType": "SNAPSHOT_BASELINE",
                "_warning": "first_run_no_baseline",
                "snapshotKey": key,
                "baselineProductCount": len(current),
            },
            counters,
        )
        return

    old = previous["items"]
    changes = 0

    for pid, entry in current.items():
        if pid not in old:
            await push(
                change_record(raw, domain, "NEW", by_id.get(pid),
                              {"price": entry["p"], "publishedAt": entry["pub"]}),
                counters,
            )
            changes += 1
            continue
        before = old[pid]
        if before.get("p") != entry["p"]:
            await push(
                change_record(raw, domain, "PRICE_CHANGED", by_id.get(pid), {
                    "priceBefore": before.get("p"),
                    "priceAfter": entry["p"],
                    "priceDelta": _delta(before.get("p"), entry["p"]),
                }),
                counters,
            )
            changes += 1
        if before.get("a") != entry["a"]:
            await push(
                change_record(
                    raw, domain,
                    "BACK_IN_STOCK" if entry["a"] else "OUT_OF_STOCK",
                    by_id.get(pid),
                    {"inStockBefore": before.get("a"), "inStockAfter": entry["a"]},
                ),
                counters,
            )
            changes += 1

    for pid, before in old.items():
        if pid not in current:
            await push(
                change_record(raw, domain, "REMOVED", None, {
                    "productId": pid,
                    "title": before.get("t"),
                    "handle": before.get("h"),
                    "lastKnownPrice": before.get("p"),
                }),
                counters,
            )
            changes += 1

    await store.set_value(key, {"capturedAt": _now_iso(), "items": current})
    await push(
        {
            **store_record(profile, raw, catalogue_stats(products)),
            "recordType": "CHANGE_SUMMARY",
            "snapshotKey": key,
            "previousCapturedAt": previous.get("capturedAt"),
            "previousProductCount": len(old),
            "currentProductCount": len(current),
            "changesDetected": changes,
        },
        counters,
    )


def _delta(before: object, after: object) -> float | None:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return round(after - before, 2)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- driver -------------------------------------------------------------------


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, InvalidStoreUrl):
        return "bad_input"
    if isinstance(exc, DomainUnreachable):
        return "domain_unreachable"
    if isinstance(exc, NotShopify):
        return "not_shopify"
    if isinstance(exc, NoCatalogueApi):
        return "no_public_catalogue"
    if isinstance(exc, NotJson):
        return "html_instead_of_json"
    if isinstance(exc, HttpError):
        return "retries_exhausted" if exc.status == 0 else f"http_{exc.status}"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    return "exception"


async def process_store(
    client: ShopifyClient, raw: str, mode: str, counters: RunCounters, opts: dict
) -> None:
    try:
        # detect only answers "is this Shopify, which theme", so it does not need
        # (or pay for) a catalogue probe.
        profile = await resolve_store(client, raw, require_catalogue=(mode != "detect"))
    except RECOVERABLE as exc:
        await push(error_record(str(raw), _error_kind(exc), str(exc)), counters)
        return

    log.info(
        "%s -> shopify=%s (%s) theme=%s api=%s",
        profile.requested_domain,
        profile.is_shopify,
        profile.confidence,
        (profile.theme or {}).get("themeName"),
        profile.api_origin,
    )

    try:
        if mode == "detect":
            await run_detect(client, profile, raw, counters)
        elif mode == "store-analysis":
            await run_store_analysis(client, profile, raw, counters, opts)
        elif mode == "products":
            await run_products(client, profile, raw, counters, opts)
        elif mode == "new-products":
            await run_new_products(client, profile, raw, counters, opts)
        elif mode == "collections":
            await run_collections(client, profile, raw, counters, opts)
        elif mode == "changes":
            await run_changes(client, profile, raw, counters, opts)
        else:
            raise ValueError(f"Unknown mode {mode!r}")
    except RECOVERABLE as exc:
        await push(error_record(str(raw), _error_kind(exc), str(exc)), counters)
        return
    counters.stores_ok += 1


async def _maybe_proxy_url(proxy_input: object) -> str | None:
    """Resolve a proxy URL, or None to go direct.

    Shopify storefronts have no anti-bot layer, so a proxy is optional and the
    default input leaves it off. Building a ProxyConfiguration unconditionally
    makes the SDK demand an Apify proxy password and kills runs that never
    wanted a proxy.
    """
    if not isinstance(proxy_input, dict):
        return None
    if not (proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls")):
        return None
    try:
        config = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
    except Exception as exc:
        log.warning("Proxy configuration failed (%r) -- continuing without a proxy.", exc)
        return None
    return await config.new_url() if config else None


def _wire_logging() -> None:
    apify_logger = logging.getLogger("apify")
    for name in ("shopify", "src.client", "src.resolver"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            for handler in apify_logger.handlers:
                logger.addHandler(handler)
        logger.propagate = not logger.handlers


async def main() -> None:
    async with Actor:
        _wire_logging()
        raw_input = await Actor.get_input() or {}

        mode = (raw_input.get("mode") or "store-analysis").strip()
        if mode not in MODES:
            raise input_error(f"Unknown mode {mode!r}. Valid: {sorted(MODES)}")

        store_urls = raw_input.get("storeUrls") or []
        if not store_urls:
            raise input_error("`storeUrls` is required -- give at least one Shopify store URL.")

        max_products_raw = raw_input.get("maxProducts")
        opts = {
            "maxProducts": None if max_products_raw in (None, 0) else int(max_products_raw),
            "newWithinDays": max(1, int(raw_input.get("newWithinDays") or 7)),
            "newestProducts": max(0, int(raw_input.get("newestProducts") or 10)),
            "explodeVariants": bool(raw_input.get("explodeVariants")),
        }
        max_concurrency = max(1, min(int(raw_input.get("maxConcurrency") or 4), 16))

        proxy_url = await _maybe_proxy_url(raw_input.get("proxyConfiguration"))
        log.info(
            "Mode=%s stores=%d concurrency=%d proxy=%s opts=%s",
            mode, len(store_urls), max_concurrency, bool(proxy_url), opts,
        )

        counters = RunCounters()
        semaphore = asyncio.Semaphore(max_concurrency)

        async with ShopifyClient(proxy_url=proxy_url) as client:

            async def bounded(raw):
                async with semaphore:
                    await process_store(client, raw, mode, counters, opts)

            await asyncio.gather(*(bounded(u) for u in store_urls))

        log.info(
            "Done. stores_ok=%d pushed=%d errors=%d",
            counters.stores_ok, counters.pushed, counters.errors,
        )
        await Actor.set_value(
            "RUN_SUMMARY",
            {
                "mode": mode,
                "storesRequested": len(store_urls),
                "storesSucceeded": counters.stores_ok,
                "pushed": counters.pushed,
                "errors": counters.errors,
            },
        )
