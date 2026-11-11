"""Steam Community Market scraper -- Apify actor entry point.

One actor, six modes, because every mode reads the same anonymous RPC layer
with the same currency semantics (exit-IP country) and the same item identity
(appid + market_hash_name). The item modes can also take their item list from
a search, so "price history of the 50 most popular CS2 cases" is one run.

    search        catalogue browse/search             1 request per 100 items
    itemOverview  description + order book + price stats  3 requests per item
    priceHistory  full median-price/volume series      1 request per item
    orderBook     full-depth buy/sell order book       1 request per item
    listings      individual sell listings (float, seed, stickers)  1 per 20
    recentSales   live global feed of completed sales  1 request per poll
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from apify import Actor

from src.client import BadArguments, SteamClient, SteamError
from src.constants import (
    ACTIONS_ROUTE,
    ITEM_MODES,
    LISTING_SORTS,
    LISTINGS_PAGE_SIZE,
    MAX_LISTINGS_PER_ITEM,
    MAX_SEARCH_ITEMS,
    MODES,
    ORDERBOOK_ROUTE,
    SEARCH_PAGE_SIZE,
    SEARCH_SORTS,
)
from src.records import (
    currency_code,
    description_fields,
    envelope,
    error_record,
    expand_levels,
    history_points,
    history_stats,
    listing_extras,
    market_url,
    orderbook_summary,
    sale_extras,
    search_extras,
    slim_listing,
)
from src.runtime import (
    ItemRef,
    clamp,
    dedupe,
    optional_float,
    parse_item,
    proxy_factory_from,
    resolve_app,
    string_list,
)
from src.input_errors import input_error

Emit = Callable[[list[dict]], Awaitable[None]]


# -- search ----------------------------------------------------------------


def _search_body(inp: dict, appid: int) -> dict:
    body: dict[str, Any] = {
        "appid": appid,
        "strQuery": (inp.get("searchQuery") or "").strip(),
        "filters": {},
        "start": 0,
        "count": SEARCH_PAGE_SIZE,
    }
    filters = inp.get("searchFilters") or {}
    if not isinstance(filters, dict):
        raise ValueError('searchFilters must be an object like {"Type": ["CSGO_Type_WeaponCase"]}')
    for category, tags in filters.items():
        body["filters"][str(category)] = [str(t) for t in (tags if isinstance(tags, list) else [tags])]
    sort = inp.get("sortBy") or "popular"
    if sort not in SEARCH_SORTS:
        raise ValueError(f"Unknown sortBy {sort!r}. Choose one of: {', '.join(SEARCH_SORTS)}")
    body["sort"], body["direction"] = SEARCH_SORTS[sort]
    lo, hi = inp.get("minPrice"), inp.get("maxPrice")
    if lo not in (None, "") or hi not in (None, ""):
        # Search prices in USD regardless of exit IP (verified: eCurrency 1
        # from an Indonesian IP), and the filter takes USD cents.
        body["price"] = {
            "unMin": int(round(float(lo or 0) * 100)),
            "unMax": int(round(float(hi) * 100)) if hi not in (None, "") else 0,
            "eCurrency": 1,
        }
    return body


async def iter_search(client: SteamClient, inp: dict, appid: int, max_items: int, log):
    """Yield raw search rows, page by page, up to max_items."""
    body = _search_body(inp, appid)
    seen = 0
    total = None
    while seen < max_items:
        data = await client.query(ACTIONS_ROUTE, "Search", body)
        if data is None:
            raise SteamError(f"Search returned no data for appid {appid} (unknown or non-market app?)")
        rows = data.get("results") or []
        total = data.get("total_count")
        if body["start"] == 0:
            log.info(f"Search appid={appid} query={body['strQuery']!r}: {total} matching item groups")
        if not rows:
            break
        rows = rows[: max_items - seen]
        seen += len(rows)
        yield rows
        body["start"] += len(data.get("results") or [])
        if total is not None and body["start"] >= total:
            break


async def run_search(client: SteamClient, inp: dict, emit: Emit, log) -> int:
    appid = resolve_app(inp.get("appId"))
    max_items = clamp(inp.get("maxItems"), 1, MAX_SEARCH_ITEMS, 100)
    label = inp.get("searchQuery") or f"app:{appid}"
    count = 0
    async for rows in iter_search(client, inp, appid, max_items, log):
        await emit([envelope(label, "ITEM", {**row, **search_extras(row)}) for row in rows])
        count += len(rows)
    return count


# -- item resolution ---------------------------------------------------------


async def expand_group(client: SteamClient, ref: ItemRef) -> list[ItemRef]:
    """A skin or bucket group -> every variant (wear / StatTrak / Souvenir)."""
    data = await client.route_buckets(ref.appid, ref.name)
    buckets = (data or {}).get("buckets") or []
    variants = [ItemRef(ref.raw, ref.appid, b["bucket_id"]) for b in buckets if b.get("bucket_id")]
    return variants


async def resolve_items(client: SteamClient, inp: dict, mode: str, log) -> tuple[list[ItemRef], list[dict]]:
    default_app = resolve_app(inp.get("appId"))
    errors: list[dict] = []
    refs: list[ItemRef] = []
    for raw in dedupe(string_list(inp.get("items"))):
        try:
            refs.append(parse_item(raw, default_app))
        except ValueError as exc:
            errors.append(error_record(raw, "invalid_input", f"{exc}. Use a market_hash_name or a steamcommunity.com/market/listings/... URL."))

    if not refs and not errors:
        # No explicit items: take them from a search.
        max_items = clamp(inp.get("maxItems"), 1, MAX_SEARCH_ITEMS, 100)
        log.info(f"No items given -- selecting the top {max_items} from a search.")
        async for rows in iter_search(client, inp, default_app, max_items, log):
            for row in rows:
                name = row.get("strHash") or (row.get("asset_description") or {}).get("market_hash_name")
                if name:
                    refs.append(ItemRef(f"search:{name}", default_app, name))

    expand = bool(inp.get("expandVariants"))
    out: list[ItemRef] = []
    for ref in refs:
        # Listings mode can query a bucket group directly; the other modes are
        # keyed by an exact hash name, so a group always has to be expanded.
        if ref.is_group and mode == "listings" and not expand:
            out.append(ref)
            continue
        if ref.is_group or expand:
            try:
                variants = await expand_group(client, ref)
            except SteamError as exc:
                errors.append(error_record(ref.raw, "expand_failed", str(exc)))
                continue
            if variants:
                log.info(f"{ref.name}: expanded to {len(variants)} variant(s)")
                out.extend(variants)
                continue
            if ref.is_group:
                errors.append(error_record(ref.raw, "item_not_found", f"Bucket group {ref.name} has no variants."))
                continue
        out.append(ref)
    return dedupe(out), errors


# -- per-item modes ----------------------------------------------------------


def not_found(ref: ItemRef) -> dict:
    return error_record(
        ref.raw,
        "item_not_found",
        f"No market item named {ref.name!r} in app {ref.appid}. Names are the exact "
        "market_hash_name, case- and punctuation-sensitive (e.g. 'AK-47 | Redline (Field-Tested)').",
    )


async def item_overview(client: SteamClient, ref: ItemRef, inp: dict) -> list[dict]:
    desc, book, history = await asyncio.gather(
        client.query(ACTIONS_ROUTE, "QueryDescription", ref.appid, ref.name),
        client.query(ORDERBOOK_ROUTE, "Load", ref.appid, ref.name),
        client.query(ACTIONS_ROUTE, "QueryPriceHistory", ref.appid, ref.name),
    )
    if not desc:
        return [not_found(ref)]
    book_data = (book or {}).get("data") if (book or {}).get("success") else None
    payload = {
        "appid": ref.appid,
        "marketHashName": ref.name,
        **description_fields(desc),
        **(orderbook_summary(book_data) if book_data else {}),
        **history_stats(history or {}),
        "historyCurrency": currency_code((history or {}).get("ecurrency")),
        "marketUrl": market_url(ref.appid, ref.name),
    }
    if book_data:
        # A preview only: the overview row stays small. Mode orderBook has depth.
        depth = min(clamp(inp.get("orderBookDepth"), 0, 100_000, 10) or 10, 10)
        payload["buyOrders"] = expand_levels(book_data.get("rgCompactBuyOrders"), depth)
        payload["sellOrders"] = expand_levels(book_data.get("rgCompactSellOrders"), depth)
    return [envelope(ref.raw, "ITEM_OVERVIEW", payload)]


async def price_history(client: SteamClient, ref: ItemRef, inp: dict) -> list[dict]:
    data = await client.query(ACTIONS_ROUTE, "QueryPriceHistory", ref.appid, ref.name)
    if data is None:
        return [not_found(ref)]
    days = clamp(inp.get("historyDays"), 0, 100_000, 0)
    points = history_points(data, days)
    currency = currency_code(data.get("ecurrency"))
    base = {"appid": ref.appid, "marketHashName": ref.name, "currency": currency, "ecurrency": data.get("ecurrency")}
    if (inp.get("historyOutput") or "perItem") == "perPoint":
        return [envelope(ref.raw, "PRICE_POINT", {**base, **p}) for p in points]
    return [
        envelope(
            ref.raw,
            "PRICE_HISTORY",
            {**base, **history_stats(data), "marketUrl": market_url(ref.appid, ref.name), "prices": points},
        )
    ]


async def order_book(client: SteamClient, ref: ItemRef, inp: dict) -> list[dict]:
    resp = await client.query(ORDERBOOK_ROUTE, "Load", ref.appid, ref.name)
    if not resp or not resp.get("success") or not resp.get("data"):
        return [not_found(ref)]
    book = resp["data"]
    depth = clamp(inp.get("orderBookDepth"), 0, 100_000, 50)
    raw = {k: v for k, v in book.items() if not k.startswith("rgCompact")}
    return [
        envelope(
            ref.raw,
            "ORDER_BOOK",
            {
                "appid": ref.appid,
                "marketHashName": ref.name,
                **raw,
                **orderbook_summary(book),
                "buyOrders": expand_levels(book.get("rgCompactBuyOrders"), depth),
                "sellOrders": expand_levels(book.get("rgCompactSellOrders"), depth),
                "marketUrl": market_url(ref.appid, ref.name),
            },
        )
    ]


async def listings(client: SteamClient, ref: ItemRef, inp: dict) -> list[dict]:
    max_rows = clamp(inp.get("maxListingsPerItem"), 1, MAX_LISTINGS_PER_ITEM, 100)
    sort_key = inp.get("listingSort") or "priceAsc"
    if sort_key not in LISTING_SORTS:
        raise ValueError(f"Unknown listingSort {sort_key!r}. Choose one of: {', '.join(LISTING_SORTS)}")
    min_float = optional_float(inp.get("minFloat"), "minFloat")
    max_float = optional_float(inp.get("maxFloat"), "maxFloat")
    keep_desc = bool(inp.get("includeFullDescription"))
    body: dict[str, Any] = {
        "appid": ref.appid,
        "strItemName": ref.name,
        "filters": {},
        "accessoryFilters": {},
        "propertyFilters": {},
        "start": 0,
        "sort": LISTING_SORTS[sort_key],
    }
    if not ref.is_group:
        body["disableGrouping"] = True  # the exact variant, not its whole group

    out: list[dict] = []
    total = None
    seen_ids: set[str] = set()
    while len(out) < max_rows:
        data = await client.query(ACTIONS_ROUTE, "QueryListingsForItem", body)
        if data is None:
            break
        total = data.get("total_count")
        page = data.get("listings") or []
        stop = False
        for listing in page:
            lid = str(listing.get("listingid"))
            if lid in seen_ids:  # pages shift as listings sell mid-crawl
                continue
            seen_ids.add(lid)
            extras = listing_extras(listing)
            fv = extras.get("floatValue")
            if fv is not None:
                if min_float is not None and fv < min_float:
                    continue
                if max_float is not None and fv > max_float:
                    stop = sort_key == "floatAsc"  # sorted: nothing further qualifies
                    if stop:
                        break
                    continue
            out.append(envelope(ref.raw, "LISTING", {**slim_listing(listing, keep_desc), **extras, "listingRank": len(out) + 1}))
            if len(out) >= max_rows:
                break
        if stop or not data.get("more") or not page:
            break
        body["start"] += len(page)

    if not out and seen_ids:
        return [error_record(ref.raw, "no_matching_listings",
                             f"{len(seen_ids)} listing(s) scanned, none inside the float range "
                             f"[{min_float if min_float is not None else 0}, {max_float if max_float is not None else 1}].")]
    if not out:
        # Zero rows is ambiguous: wrong name, a commodity (which reports
        # total_count 1 with an empty page), or simply sold out. One
        # description lookup tells them apart -- never return nothing.
        if ref.is_group:
            return [error_record(ref.raw, "no_listings", "This bucket group has no active sell listings right now.")]
        desc = await client.query(ACTIONS_ROUTE, "QueryDescription", ref.appid, ref.name)
        if not desc:
            return [not_found(ref)]
        if desc.get("commodity"):
            return [error_record(ref.raw, "commodity_no_listings",
                                 "This is a commodity item (case, key, sticker...): Steam sells it from an "
                                 "order book, not individual listings. Use mode 'orderBook' instead.")]
        return [error_record(ref.raw, "no_listings", "The item exists but has no active sell listings right now.")]
    return out


ITEM_HANDLERS = {
    "itemOverview": item_overview,
    "priceHistory": price_history,
    "orderBook": order_book,
    "listings": listings,
}


async def run_items(client: SteamClient, inp: dict, mode: str, emit: Emit, log) -> int:
    refs, errors = await resolve_items(client, inp, mode, log)
    if errors:
        await emit(errors)
    if not refs:
        log.warning("No items to process.")
        return len(errors)
    log.info(f"{mode}: processing {len(refs)} item(s)")
    handler = ITEM_HANDLERS[mode]
    count = len(errors)
    done = 0

    async def one(ref: ItemRef) -> None:
        nonlocal count, done
        try:
            records = await handler(client, ref, inp)
        except BadArguments as exc:
            records = [error_record(ref.raw, "api_contract_changed", str(exc))]
        except SteamError as exc:
            records = [error_record(ref.raw, "request_failed", str(exc))]
        await emit(records)
        count += len(records)
        done += 1
        if done % 25 == 0 or done == len(refs):
            log.info(f"{mode}: {done}/{len(refs)} items done, {count} records")

    await asyncio.gather(*(one(r) for r in refs))
    return count


# -- recent sales ------------------------------------------------------------


async def run_recent_sales(client: SteamClient, inp: dict, emit: Emit, log) -> int:
    polls = clamp(inp.get("recentSalesPolls"), 1, 720, 1)
    interval = clamp(inp.get("recentSalesIntervalSecs"), 10, 3600, 30)
    app_filter = resolve_app(inp.get("appId")) if inp.get("filterRecentSalesByApp") else None
    seen: set[str] = set()
    count = 0
    for i in range(polls):
        data = await client.query(ACTIONS_ROUTE, "QueryRecentSales")
        sales = (data or {}).get("rgSales") or []
        fresh = []
        for sale in sales:
            key = sale.get("strKey") or str((sale.get("listing") or {}).get("listingid"))
            if key in seen:
                continue
            seen.add(key)
            extras = sale_extras(sale)
            if app_filter and extras.get("appid") != app_filter:
                continue
            listing = slim_listing(sale.get("listing") or {}, bool(inp.get("includeFullDescription")))
            # unPrice/strSubtotal on a *sold* listing are always 0 -- the real
            # price is strSoldPrice -- so the misleading zeros are dropped.
            for k in ("unPrice", "unFee", "strSubtotal"):
                listing.pop(k, None)
            fresh.append(envelope("recentSales", "SALE", {**{k: v for k, v in sale.items() if k != "listing"}, "listing": listing, **extras}))
        if fresh:
            await emit(fresh)
        count += len(fresh)
        log.info(f"recentSales poll {i + 1}/{polls}: {len(sales)} sales, {len(fresh)} new")
        if i + 1 < polls:
            await asyncio.sleep(interval)
    return count


# -- entry -------------------------------------------------------------------


async def run_mode(client: SteamClient, inp: dict, mode: str, emit: Emit, log) -> int:
    if mode == "search":
        return await run_search(client, inp, emit, log)
    if mode in ITEM_MODES:
        return await run_items(client, inp, mode, emit, log)
    return await run_recent_sales(client, inp, emit, log)


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        log = Actor.log
        mode = (inp.get("mode") or "search").strip()
        if mode not in MODES:
            raise input_error(f"Unknown mode {mode!r}. Choose one of: {', '.join(MODES)}")

        proxy_factory = await proxy_factory_from(Actor, inp)
        client = SteamClient(
            proxy_factory=proxy_factory,
            max_concurrency=clamp(inp.get("maxConcurrency"), 1, 16, 4),
            log=log,
        )

        async def emit(records: list[dict]) -> None:
            if records:
                await Actor.push_data(records)

        try:
            total = await run_mode(client, inp, mode, emit, log)
        except (BadArguments, SteamError) as exc:
            log.error(f"{mode}: {exc}")
            await emit([error_record(mode, "request_failed", str(exc))])
            total = 1
        finally:
            await client.close()
        log.info(f"Finished mode {mode!r}: {total} record(s), {client.requests_made} HTTP request(s).")
