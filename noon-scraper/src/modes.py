"""The eight scraping modes.

All three listing modes -- search, category, brand -- hit the SAME endpoint
shape, so they share one pagination walker. What differs is only the path and
which query parameters are legal.

Pagination contract (measured, see constants.py):
  * `limit` is honoured to 200 and clamped there.
  * `page` is clamped to 50 server-side.
  * Past the end the API returns 200 with an EMPTY hits array, never a 404.
So the stop condition is an empty page, plus the caller's item budget. `nbPages`
is NOT trusted: it is derived from an approximate counter that drifts between
identical calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable

from .client import NoonBlocked, NoonClient, NoonNotFound
from .constants import (
    BRAND_PARAM,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_PAGE,
    PRICE_MAX_PARAM,
    PRICE_MIN_PARAM,
    SORT_BY_PARAM,
    SORT_DIR_PARAM,
)
from .parsers import (
    clean_category_path,
    currency_of,
    envelope,
    error_record,
    extract_category_tree,
    extract_facets,
    extract_hits,
    extract_instant_products,
    extract_offers,
    listing_meta,
    parse_sku,
    product_record,
    rating_of,
    site_url,
)

log = logging.getLogger("noon.modes")

S1 = "S1-mp-catalog"        # marketplace via the Minutes gateway
S1_INSTANT = "S1-instant-catalog"


class Budget:
    """A shared item cap, so every mode stops fetching at the same moment."""

    def __init__(self, max_items: int) -> None:
        self.max_items = max(0, int(max_items or 0))
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return bool(self.max_items) and self.used >= self.max_items

    def take(self, n: int = 1) -> bool:
        if self.exhausted:
            return False
        self.used += n
        return True

    def remaining(self) -> int | None:
        return (self.max_items - self.used) if self.max_items else None


# --- shared helpers -----------------------------------------------------

def _listing_params(options: dict[str, Any], *, allow_query: bool) -> dict[str, Any]:
    """Build the query string for a listing request.

    Only parameters proven to bite are sent. `f[filter_attr_brand]` is
    deliberately absent -- it is silently ignored upstream (see constants.py
    DECOYS); the real brand filter is the top-level `brand`.
    """
    params: dict[str, Any] = {}
    limit = int(options.get("limitPerPage") or DEFAULT_LIMIT)
    params["limit"] = max(1, min(limit, MAX_LIMIT))

    sort_by = (options.get("sortBy") or "").strip()
    if sort_by and sort_by != "popularity":
        params[SORT_BY_PARAM] = sort_by
        params[SORT_DIR_PARAM] = (options.get("sortDir") or "desc").strip()

    if options.get("priceMin") not in (None, ""):
        params[PRICE_MIN_PARAM] = options["priceMin"]
    if options.get("priceMax") not in (None, ""):
        params[PRICE_MAX_PARAM] = options["priceMax"]

    brand = (options.get("brandFilter") or "").strip()
    if brand and allow_query:
        params[BRAND_PARAM] = brand
    return params


async def _walk_listing(
    client: NoonClient,
    *,
    path: str,
    base_params: dict[str, Any],
    locale: str,
    country: str,
    language: str,
    input_value: str,
    budget: Budget,
    max_pages: int,
    on_first_page: Callable[[dict[str, Any]], None] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Page through a listing endpoint until it runs dry or the budget ends."""
    seen: set[str] = set()
    pages = max(1, min(int(max_pages or MAX_PAGE), MAX_PAGE))
    for page in range(1, pages + 1):
        if budget.exhausted:
            return
        params = dict(base_params)
        if page > 1:
            params["page"] = page
        try:
            payload = await client.catalog_page(path, locale=locale, params=params)
        except NoonNotFound as exc:
            yield error_record(input_value, "not_found", str(exc),
                               country=country, language=language)
            return
        except NoonBlocked as exc:
            yield error_record(input_value, "blocked", str(exc),
                               country=country, language=language)
            return

        if page == 1 and on_first_page is not None:
            on_first_page(payload)

        hits = extract_hits(payload)
        if not hits:
            # The documented end-of-results signal: 200 with an empty array.
            log.info("[%s] page %d empty -- end of results.", input_value, page)
            return

        meta = listing_meta(payload)
        new_on_page = 0
        for hit in hits:
            sku = str(hit.get("sku") or hit.get("offer_code") or "")
            if sku and sku in seen:
                continue
            if sku:
                seen.add(sku)
            if not budget.take():
                return
            new_on_page += 1
            yield product_record(
                hit, input_value=input_value, source=S1,
                country=country, language=language, page=page, meta=meta,
            )
        log.info("[%s] page %d -> %d products (%d new, %d total)",
                 input_value, page, len(hits), new_on_page, budget.used)
        if new_on_page == 0:
            # Every row was a duplicate of an earlier page: the endpoint has
            # started repeating itself, which is the other way it signals the
            # end. Stop rather than spin.
            log.info("[%s] page %d was all duplicates -- stopping.", input_value, page)
            return


# --- modes --------------------------------------------------------------

async def mode_search(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    country, language = options["country"], options["language"]
    locale = options["locale"]
    for keyword in options.get("searchKeywords") or []:
        params = _listing_params(options, allow_query=True)
        params["q"] = keyword
        async for rec in _walk_listing(
            client, path="/search/", base_params=params, locale=locale,
            country=country, language=language, input_value=keyword,
            budget=budget, max_pages=options.get("maxPages"),
        ):
            yield rec


async def mode_category(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    country, language = options["country"], options["language"]
    locale = options["locale"]
    for raw in options.get("categoryPaths") or []:
        path = clean_category_path(raw)
        if not path:
            yield error_record(raw, "bad_input",
                               "Could not read a category path out of this value.",
                               country=country, language=language)
            continue
        async for rec in _walk_listing(
            client, path=f"/{path}/", base_params=_listing_params(options, allow_query=True),
            locale=locale, country=country, language=language, input_value=raw,
            budget=budget, max_pages=options.get("maxPages"),
        ):
            yield rec


async def mode_brand(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    country, language = options["country"], options["language"]
    locale = options["locale"]
    for raw in options.get("brandCodes") or []:
        code = clean_category_path(raw).replace("brand/", "").strip("/")
        if not code:
            yield error_record(raw, "bad_input", "Empty brand code.",
                               country=country, language=language)
            continue
        async for rec in _walk_listing(
            client, path=f"/brand/{code}/",
            base_params=_listing_params(options, allow_query=False),
            locale=locale, country=country, language=language, input_value=raw,
            budget=budget, max_pages=options.get("maxPages"),
        ):
            yield rec


async def _fetch_products(
    client: NoonClient, options: dict[str, Any], budget: Budget,
    *, emit: Callable[[str, dict[str, Any]], list[dict[str, Any]]],
) -> AsyncIterator[dict[str, Any]]:
    """Shared fan-out for the two SKU-driven modes (product, offers).

    Concurrency is bounded by a semaphore -- the gateway took 10 in flight
    without complaint during recon, but a scraper should not be the reason a
    limit gets added.
    """
    country, language = options["country"], options["language"]
    locale = options["locale"]
    sem = asyncio.Semaphore(int(options.get("concurrency") or 4))

    async def one(raw: str) -> list[dict[str, Any]]:
        sku = parse_sku(raw)
        if not sku:
            return [error_record(
                raw, "bad_input",
                "No noon SKU found in this value. Pass a SKU like N70211544V "
                "or a product URL ending in /<SKU>/p/.",
                country=country, language=language)]
        async with sem:
            try:
                payload = await client.product_detail(sku, locale=locale)
            except NoonNotFound as exc:
                return [error_record(raw, "not_found", str(exc),
                                     country=country, language=language)]
            except NoonBlocked as exc:
                return [error_record(raw, "blocked", str(exc),
                                     country=country, language=language)]
        return emit(raw, payload)

    targets = options.get("productSkus") or []
    for chunk_start in range(0, len(targets), 20):
        if budget.exhausted:
            return
        chunk = targets[chunk_start:chunk_start + 20]
        for rows in await asyncio.gather(*(one(t) for t in chunk)):
            for row in rows:
                if not budget.take():
                    return
                yield row


async def mode_product(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    country, language = options["country"], options["language"]

    def emit(raw: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        product = payload.get("product") or {}
        if not product:
            return [error_record(raw, "empty_payload",
                                 "200 from the PDP endpoint but no product object.",
                                 country=country, language=language)]
        offers = extract_offers(payload)
        prices = [o.get("sale_price") or o.get("price") for o in offers]
        prices = [p for p in prices if isinstance(p, (int, float))]
        rec = envelope(
            raw, S1, "PRODUCT_DETAIL", country=country, language=language,
            extra={
                "currency": currency_of(country),
                "productUrl": site_url(product.get("sku"),
                                       (offers[0].get("url") if offers else None),
                                       country, language),
                "offerCount": len(offers),
                "lowestOfferPrice": min(prices) if prices else None,
                "highestOfferPrice": max(prices) if prices else None,
                "rating": rating_of(payload),
                "canonical_url": payload.get("canonical_url"),
            },
        )
        rec.update(product)
        return [rec]

    async for rec in _fetch_products(client, options, budget, emit=emit):
        yield rec


async def mode_offers(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    country, language = options["country"], options["language"]

    def emit(raw: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        product = payload.get("product") or {}
        offers = extract_offers(payload)
        if not offers:
            return [error_record(raw, "no_offers",
                                 "The product exists but currently lists no "
                                 "buyable seller offers.",
                                 country=country, language=language)]
        rows = []
        for rank, offer in enumerate(offers, start=1):
            rec = envelope(
                raw, S1, "OFFER", country=country, language=language,
                extra={
                    "currency": currency_of(country),
                    "offerRank": rank,
                    "offerCount": len(offers),
                    "product_sku": product.get("sku"),
                    "product_title": product.get("product_title"),
                    "brand": product.get("brand"),
                    "product_rating": product.get("product_rating"),
                },
            )
            rec.update(offer)
            rows.append(rec)
        return rows

    async for rec in _fetch_products(client, options, budget, emit=emit):
        yield rec


async def mode_category_tree(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    """noon's category hierarchy.

    There is no navigation endpoint (`/api/u/navigation/` 404s), but every
    listing response carries the full tree in its `category` facet, so one
    request per root yields the whole hierarchy beneath it.
    """
    country, language = options["country"], options["language"]
    locale = options["locale"]
    roots = options.get("categoryPaths") or ["electronics-and-mobiles"]
    for raw in roots:
        path = clean_category_path(raw)
        try:
            payload = await client.catalog_page(
                f"/{path}/", locale=locale, params={"limit": 1}
            )
        except (NoonNotFound, NoonBlocked) as exc:
            yield error_record(raw, "not_found", str(exc),
                               country=country, language=language)
            continue
        rows = extract_category_tree(payload)
        if not rows:
            yield error_record(raw, "empty_payload",
                               "No category facet in this response.",
                               country=country, language=language)
            continue
        for node in rows:
            if not budget.take():
                return
            rec = envelope(raw, S1, "CATEGORY", country=country, language=language)
            rec.update(node)
            yield rec
        log.info("[%s] category tree -> %d nodes", raw, len(rows))


async def mode_facets(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    """Filter dimensions and their option counts for a query or category.

    Useful on its own for market research: the brand facet is effectively a
    ranked list of who competes in a category.
    """
    country, language = options["country"], options["language"]
    locale = options["locale"]
    targets = [("search", k) for k in (options.get("searchKeywords") or [])]
    targets += [("category", c) for c in (options.get("categoryPaths") or [])]
    for kind, raw in targets:
        params = _listing_params(options, allow_query=kind == "search")
        params["limit"] = 1
        if kind == "search":
            params["q"] = raw
            path = "/search/"
        else:
            path = f"/{clean_category_path(raw)}/"
        try:
            payload = await client.catalog_page(path, locale=locale, params=params)
        except (NoonNotFound, NoonBlocked) as exc:
            yield error_record(raw, "not_found", str(exc),
                               country=country, language=language)
            continue
        facets = extract_facets(payload)
        if not facets:
            yield error_record(raw, "empty_payload", "No facets in this response.",
                               country=country, language=language)
            continue
        for facet in facets:
            if not budget.take():
                return
            rec = envelope(raw, S1, "FACET", country=country, language=language,
                           extra={"target": kind, "nbHits": payload.get("nbHits")})
            rec.update(facet)
            yield rec


async def mode_minutes_search(client, options, budget) -> AsyncIterator[dict[str, Any]]:
    """noon Minutes (15-minute grocery) search.

    Separate catalogue, separate service, separate response shape -- and
    warehouse-scoped, so results reflect one dark store's stock rather than a
    whole country.
    """
    country, language = options["country"], options["language"]
    locale = options["locale"]
    zone = {
        k: v for k, v in {
            "x-lat": options.get("instantLat"),
            "x-lng": options.get("instantLng"),
            "x-ecom-zonecode": options.get("instantEcomZone"),
            "x-nooninstant-zonecode": options.get("instantZoneCode"),
        }.items() if v
    }
    pages = max(1, min(int(options.get("maxPages") or 10), MAX_PAGE))
    for keyword in options.get("searchKeywords") or []:
        seen: set[str] = set()
        for page in range(1, pages + 1):
            if budget.exhausted:
                return
            params: dict[str, Any] = {"q": keyword}
            if page > 1:
                params["page"] = page
            try:
                payload = await client.instant_page(
                    "/search", locale=locale, params=params, zone=zone
                )
            except NoonNotFound as exc:
                yield error_record(keyword, "not_found", str(exc),
                                   country=country, language=language)
                break
            except NoonBlocked as exc:
                yield error_record(keyword, "blocked", str(exc),
                                   country=country, language=language)
                break

            products = extract_instant_products(payload)
            if not products:
                log.info("[%s] Minutes page %d empty -- end of results.", keyword, page)
                break
            new_on_page = 0
            for product in products:
                sku = str(product.get("sku") or "")
                if sku and sku in seen:
                    continue
                if sku:
                    seen.add(sku)
                if not budget.take():
                    return
                new_on_page += 1
                rec = envelope(
                    keyword, S1_INSTANT, "INSTANT_PRODUCT",
                    country=country, language=language,
                    extra={
                        "currency": currency_of(country),
                        "page": page,
                        "whCode": payload.get("whCode"),
                        "nbHits": payload.get("nbHits"),
                        "nbPages": payload.get("nbPages"),
                    },
                )
                rec.update(product)
                yield rec
            log.info("[%s] Minutes page %d -> %d products (%d new)",
                     keyword, page, len(products), new_on_page)
            if new_on_page == 0:
                break


MODES: dict[str, Callable[..., AsyncIterator[dict[str, Any]]]] = {
    "search": mode_search,
    "category": mode_category,
    "brand": mode_brand,
    "product": mode_product,
    "offers": mode_offers,
    "categoryTree": mode_category_tree,
    "facets": mode_facets,
    "minutesSearch": mode_minutes_search,
}

# Which input array each mode needs at least one value in.
MODE_REQUIRED_INPUT: dict[str, tuple[str, ...]] = {
    "search": ("searchKeywords",),
    "category": ("categoryPaths",),
    "brand": ("brandCodes",),
    "product": ("productSkus",),
    "offers": ("productSkus",),
    "categoryTree": (),                       # defaults to a root category
    "facets": ("searchKeywords", "categoryPaths"),
    "minutesSearch": ("searchKeywords",),
}
