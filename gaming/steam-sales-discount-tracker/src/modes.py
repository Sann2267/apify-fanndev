"""One async generator per mode. Each yields finished records (envelope included)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator

from .client import Blocked, NotFound, SteamClient
from .constants import (
    APPDETAILS_BATCH,
    COMPLETE_COVERAGE,
    CATEGORY1,
    SEARCH_PAGE_SIZE,
    SORT_BY,
    STORE,
    STORE_ITEMS_BATCH,
    URL_APPDETAILS,
    URL_ECB_FX,
    URL_EVENT_CALENDAR,
    URL_FEATURED_CATEGORIES,
    URL_POPULAR_TAGS,
    URL_SALE_PAGE,
    URL_SEARCH,
    URL_STORE_ITEMS,
    URL_STORE_SEARCH,
)
from .parsers import (
    UnexpectedShape,
    cents_to_amount,
    discount_details,
    envelope,
    error_record,
    parse_app_ref,
    parse_ecb,
    parse_event_calendar,
    parse_featured,
    parse_sale_page,
    parse_sale_ref,
    parse_search_rows,
    spotlight_target,
    store_item_key,
    unix_to_iso,
)

log = logging.getLogger("steam.modes")


@dataclass
class Options:
    country: str = "US"
    countries: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    sales: list[str] = field(default_factory=list)
    category: str = "all"
    tags: list[str] = field(default_factory=list)
    search_term: str = ""
    max_price: float | None = None
    min_discount: int = 1
    sort_by: str = "relevance"
    hide_free_to_play: bool = False
    max_items: int = 500
    include_discount_details: bool = True
    include_usd: bool = True
    include_past_events: bool = False
    concurrency: int = 4
    language: str = "english"
    # Set by the deals mode: True only when every page of the result set was read,
    # which is what makes "absent this run" mean "the deal ended".
    crawl_complete: bool = False
    total_count: int | None = None


# --------------------------------------------------------------------------- shared helpers

def _id_obj(kind: str, ident: int) -> dict[str, int]:
    return {"app": {"appid": ident}, "package": {"packageid": ident}, "bundle": {"bundleid": ident}}[kind]


async def fetch_store_items(client: SteamClient, keys: list[tuple[str, int]], country: str, opt: Options) -> dict[tuple[str, int], dict[str, Any]]:
    """GetItems for apps / packages / bundles in batches -> {(kind, id): item}. Failures degrade, never abort."""
    keys = list(dict.fromkeys(keys))
    out: dict[tuple[str, int], dict[str, Any]] = {}
    sem = asyncio.Semaphore(opt.concurrency)

    async def batch(chunk: list[tuple[str, int]]) -> None:
        body = {
            "ids": [_id_obj(k, i) for k, i in chunk],
            "context": {"language": opt.language, "country_code": country},
            "data_request": {"include_all_purchase_options": True, "include_basic_info": True, "include_release": True},
        }
        async with sem:
            try:
                data = await client.get_json(URL_STORE_ITEMS, {"input_json": json.dumps(body)})
            except (Blocked, NotFound) as exc:
                log.warning("GetItems failed for %d items (%s) - continuing without discount details", len(chunk), exc)
                return
        for item in (data.get("response") or {}).get("store_items") or []:
            key = store_item_key(item)
            if key:
                out[key] = item

    await asyncio.gather(*(batch(keys[i:i + STORE_ITEMS_BATCH]) for i in range(0, len(keys), STORE_ITEMS_BATCH)))
    return out


class Fx:
    """ECB euro reference rates -> USD conversion. Optional: failure leaves USD fields null."""

    def __init__(self) -> None:
        self.rates: dict[str, float] = {}
        self.date: str | None = None
        self.loaded = False

    async def load(self, client: SteamClient) -> None:
        if self.loaded:
            return
        self.loaded = True
        try:
            page = await client.get_page(URL_ECB_FX)
            self.date, self.rates = parse_ecb(page.text)
            log.info("ECB FX rates loaded for %s (%d currencies)", self.date, len(self.rates))
        except (Blocked, NotFound, UnexpectedShape) as exc:
            log.warning("ECB FX rates unavailable (%s) - USD fields will be null", exc)

    def to_usd(self, cents: int | None, currency: str | None) -> float | None:
        if cents is None or not currency:
            return None
        if currency == "USD":
            return round(cents / 100, 2)
        if currency not in self.rates or "USD" not in self.rates:
            return None
        return round(cents / 100 / self.rates[currency] * self.rates["USD"], 2)


FX = Fx()


_CURRENCY: dict[str, str] = {}


async def currency_for_country(client: SteamClient, appids: list[int | None], country: str) -> str | None:
    """Search HTML / GetItems carry formatted prices only; one appdetails call gives the
    ISO currency (cached per country). Tries a few appids: free/unreleased ones have no price."""
    if country in _CURRENCY:
        return _CURRENCY[country]
    ids = [a for a in dict.fromkeys(appids) if a][:20]
    if not ids:
        return None
    try:
        data = await client.get_json(URL_APPDETAILS, {"appids": ",".join(map(str, ids)), "filters": "price_overview", "cc": country})
    except (Blocked, NotFound):
        return None
    for a in ids:
        po = ((data.get(str(a)) or {}).get("data") or {})
        if isinstance(po, dict) and po.get("price_overview", {}).get("currency"):
            _CURRENCY[country] = po["price_overview"]["currency"]
            return _CURRENCY[country]
    return None


def _price_fields(final_cents: int | None, orig_cents: int | None, currency: str | None, opt: Options) -> dict[str, Any]:
    saving = (orig_cents - final_cents) if final_cents is not None and orig_cents is not None else None
    out = {
        "currency": currency,
        "finalPrice": cents_to_amount(final_cents),
        "originalPrice": cents_to_amount(orig_cents),
        "savings": cents_to_amount(saving),
        "finalPriceCents": final_cents,
        "originalPriceCents": orig_cents,
    }
    if opt.include_usd:
        out["finalPriceUsd"] = FX.to_usd(final_cents, currency)
        out["originalPriceUsd"] = FX.to_usd(orig_cents, currency)
        out["fxRateDate"] = FX.date if currency and currency != "USD" else None
    return out


def _hours_left(ends_unix: int | None) -> float | None:
    if not ends_unix:
        return None
    return round((int(ends_unix) - datetime.now(timezone.utc).timestamp()) / 3600, 1)


def _detail_fields(item: dict[str, Any] | None) -> dict[str, Any]:
    d = discount_details(item)
    d["hoursLeft"] = _hours_left(d.get("discountEndsAtUnix"))
    return d


async def resolve_tags(client: SteamClient, tags: list[str]) -> tuple[list[int], list[str]]:
    """Tag names ('Horror') or ids ('1667') -> ids. Returns (ids, unknown)."""
    ids: list[int] = []
    unknown: list[str] = []
    names = [t for t in tags if not str(t).strip().isdigit()]
    lookup: dict[str, int] = {}
    if names:
        data = await client.get_json(URL_POPULAR_TAGS)
        lookup = {str(t["name"]).casefold(): int(t["tagid"]) for t in data if isinstance(t, dict) and "tagid" in t}
    for t in tags:
        s = str(t).strip()
        if s.isdigit():
            ids.append(int(s))
        elif s.casefold() in lookup:
            ids.append(lookup[s.casefold()])
        else:
            unknown.append(s)
    return ids, unknown


async def resolve_apps(client: SteamClient, refs: list[str], country: str) -> tuple[list[tuple[str, int]], list[dict[str, Any]]]:
    resolved: list[tuple[str, int]] = []
    errors: list[dict[str, Any]] = []
    for ref in refs:
        label = str(ref).strip()
        appid, term = parse_app_ref(ref)
        if appid:
            resolved.append((label, appid))
            continue
        if not term:
            errors.append(error_record(label, "invalid_input", "Not an appid, a Steam app URL, or a game name."))
            continue
        try:
            data = await client.get_json(URL_STORE_SEARCH, {"term": term, "cc": country, "l": "english"})
        except (Blocked, NotFound) as exc:
            errors.append(error_record(label, "search_failed", str(exc)))
            continue
        hits = [it for it in data.get("items") or [] if it.get("type") == "app" and it.get("id")]
        if not hits:
            errors.append(error_record(label, "not_found", f"Steam store search returned no game for {term!r}."))
            continue
        exact = [h for h in hits if (h.get("name") or "").casefold() == term.casefold()]
        best = (exact or hits)[0]
        log.info("Resolved %r -> %s (%s)", term, best["id"], best.get("name"))
        resolved.append((label, int(best["id"])))
    seen: set[int] = set()
    return [r for r in resolved if not (r[1] in seen or seen.add(r[1]))], errors


# --------------------------------------------------------------------------- mode: deals

def _search_params(opt: Options, tag_ids: list[int], *, free_only: bool = False) -> dict[str, Any]:
    p: dict[str, Any] = {"specials": 1, "infinite": 1, "count": SEARCH_PAGE_SIZE, "cc": opt.country, "l": opt.language}
    if free_only:
        p["maxprice"] = "free"
        return p
    if CATEGORY1.get(opt.category):
        p["category1"] = CATEGORY1[opt.category]
    if tag_ids:
        p["tags"] = ",".join(map(str, tag_ids))
    if opt.search_term:
        p["term"] = opt.search_term
    if SORT_BY.get(opt.sort_by):
        p["sort_by"] = SORT_BY[opt.sort_by]
    if opt.hide_free_to_play:
        p["hidef2p"] = 1
    return p


def _row_record(label: str, source: str, rtype: str, row: dict[str, Any], currency: str | None, opt: Options,
                item: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    rec = envelope(label, source, rtype, country=opt.country, **extra)
    rec.update({k: v for k, v in row.items() if k not in ("finalPriceCents", "originalPriceCents")})
    final, orig, source_of_price = row["finalPriceCents"], row["originalPriceCents"], "search"
    best = (item or {}).get("best_purchase_option") or {}
    if not row["priceAvailable"] and best.get("final_price_in_cents") is not None:
        # Search shows some items with an EMPTY price block (e.g. an expansion sold
        # as an upgrade) while the store API still prices it: use the API values.
        final, orig = _to_int(best.get("final_price_in_cents")), _to_int(best.get("original_price_in_cents"))
        orig = orig if orig is not None else final
        rec.update(discountPct=best.get("discount_pct") or 0, finalPriceFormatted=best.get("formatted_final_price"),
                   originalPriceFormatted=best.get("formatted_original_price") or best.get("formatted_final_price"))
        source_of_price = "store_api"
    rec["priceSource"] = source_of_price if final is not None else None
    rec.update(_price_fields(final, orig, currency, opt))
    if opt.include_discount_details:
        rec.update(_detail_fields(item))
    return rec


async def _crawl_search(client: SteamClient, opt: Options, params: dict[str, Any], label: str) -> AsyncIterator[tuple[int, list[dict[str, Any]]]]:
    """Yield (total_count, new_rows) per page. Dedupes rows: adjacent pages overlap
    (~0.4% on a 4,000-row walk) because the list re-sorts while it is read."""
    seen: set[str] = set()
    start = 0
    empty_streak = 0
    total = None
    while True:
        data = await client.get_json(URL_SEARCH, {**params, "start": start})
        if not isinstance(data, dict) or data.get("success") != 1 or "results_html" not in data:
            raise UnexpectedShape(f"search/results: unexpected payload keys {list(data)[:6] if isinstance(data, dict) else type(data)}")
        total = int(data.get("total_count") or 0)
        rows = parse_search_rows(data["results_html"])
        fresh = [r for r in rows if r["itemKey"] not in seen]
        seen.update(r["itemKey"] for r in rows)
        yield total, fresh
        start += SEARCH_PAGE_SIZE
        empty_streak = empty_streak + 1 if not rows else 0
        if start >= total or empty_streak >= 2:
            # Complete = we actually saw (almost) every item, not just every page:
            # relevance order loses ~3% to re-sorting, price order ~0.6% to ties.
            coverage = len(seen) / total if total else 1.0
            opt.crawl_complete = coverage >= COMPLETE_COVERAGE
            log.info("%s: walked all %d pages (total_count=%d, unique rows=%d, coverage %.1f%%)%s", label,
                     start // SEARCH_PAGE_SIZE, total, len(seen), coverage * 100,
                     "" if opt.crawl_complete else " - INCOMPLETE: ended-deal detection will be skipped")
            return


async def deals(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Every discounted item on the Steam store (search specials=1), with filters."""
    tag_ids, unknown = await resolve_tags(client, opt.tags) if opt.tags else ([], [])
    for t in unknown:
        yield error_record(t, "invalid_input", "Unknown Steam tag name - use a name from store.steampowered.com/tag/ or a numeric tag id.")
    if opt.tags and not tag_ids:
        return
    params = _search_params(opt, tag_ids)
    label = f"deals:{opt.country}"
    if opt.sort_by == "relevance":
        # Relevance order re-sorts while a long walk is read: a full 95-page walk
        # saw only 9,153 of 9,463 items. Name order is stable (9,463/9,463), so a
        # run that wants the WHOLE list walks it alphabetically. Top-N runs keep
        # Steam's relevance order.
        probe = await client.get_json(URL_SEARCH, {**params, "start": 0, "count": 1})
        probe_total = int((probe or {}).get("total_count") or 0) if isinstance(probe, dict) else 0
        if probe_total and opt.max_items >= probe_total:
            params["sort_by"] = SORT_BY["nameAsc"]
            log.info("%s: reading all %d items - walking in name order (the only order that stays stable)", label, probe_total)
    sort_order = next((k for k, v in SORT_BY.items() if v == params.get("sort_by")), "relevance")
    if opt.include_usd:
        await FX.load(client)
    currency: str | None = None
    emitted = 0
    rank = 0
    max_cents = round(opt.max_price * 100) if opt.max_price is not None else None
    async for total, rows in _crawl_search(client, opt, params, label):
        opt.total_count = total
        if total == 0:
            yield error_record(label, "no_results", f"Steam lists 0 discounted items for these filters ({json.dumps({k: v for k, v in params.items() if k not in ('infinite', 'count', 'l')})}).")
            return
        if currency is None:
            currency = await currency_for_country(client, [r["appid"] for r in rows if r["priceAvailable"]], opt.country)
        rank_base = rank
        rank += len(rows)
        # Unpriced rows are kept for enrichment: the store API may price them
        # (filters are re-applied to the finished record below).
        keep = [r for r in rows if not r["priceAvailable"] or (
            r["discountPct"] >= opt.min_discount
            and (max_cents is None or r["finalPriceCents"] <= max_cents))]
        if not keep:
            continue
        items = await fetch_store_items(client, [(r["itemType"], r["id"]) for r in keep], opt.country, opt) if opt.include_discount_details else {}
        for pos, r in enumerate(rows, 1):
            if r not in keep:
                continue
            rec = _row_record(label, "S1-store-search-specials", "DEAL", r, currency, opt, items.get((r["itemType"], r["id"])),
                              position=rank_base + pos, sortOrder=sort_order, totalDiscounted=total)
            if rec["finalPriceCents"] is None or rec["discountPct"] < opt.min_discount or (
                    max_cents is not None and rec["finalPriceCents"] > max_cents):
                if not (opt.min_discount == 0 and max_cents is None):
                    continue
            if emitted >= opt.max_items:
                opt.crawl_complete = False  # more qualifying rows exist beyond the cap
                return
            yield rec
            emitted += 1
        await asyncio.sleep(0)


# --------------------------------------------------------------------------- mode: freebies

async def freebies(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Free-to-keep giveaways (100% off) + Free Weekends promoted on the storefront."""
    label = f"freebies:{opt.country}"
    rows: list[dict[str, Any]] = []
    async for _total, page in _crawl_search(client, opt, _search_params(opt, [], free_only=True), label):
        rows.extend(page)
    # maxprice=free with specials=1 is "discounted to 0" - keep the strict check anyway.
    keep = [r for r in rows if r["finalPriceCents"] == 0 and r["discountPct"] == 100]
    feat = parse_featured(await client.get_json(URL_FEATURED_CATEGORIES, {"cc": opt.country, "l": opt.language}))
    weekends = []
    for sp in feat["spotlights"]:
        if "free weekend" in str(sp.get("name", "")).lower():
            kind, ident = spotlight_target(sp.get("url"))
            if kind == "app" and ident and ident.isdigit():
                weekends.append((sp, int(ident)))
    keys = [(r["itemType"], r["id"]) for r in keep] + [("app", a) for _, a in weekends]
    items = await fetch_store_items(client, keys, opt.country, opt) if keys else {}
    currency = await currency_for_country(client, [r["appid"] for r in keep] + [a for _, a in weekends], opt.country) if keys else None
    for r in keep[: opt.max_items]:
        yield _row_record(label, "S1-store-search-free", "FREEBIE", r, currency, opt, items.get((r["itemType"], r["id"])),
                          freebieType="free_to_keep")
    for sp, appid in weekends:
        item = items.get(("app", appid))
        rec = envelope(label, "S1-featured-spotlight", "FREEBIE", country=opt.country, freebieType="free_weekend",
                       itemKey=f"App_{appid}", itemType="app", id=appid, appid=appid,
                       name=(item or {}).get("name"), storeUrl=f"{STORE}/app/{appid}/",
                       spotlightName=sp.get("name"), spotlightUrl=sp.get("url"))
        rec.update(_detail_fields(item))
        best = (item or {}).get("best_purchase_option") or {}
        rec.update(_price_fields(_to_int(best.get("final_price_in_cents")), _to_int(best.get("original_price_in_cents")), currency, opt))
        rec["discountPct"] = best.get("discount_pct") or 0
        rec["finalPriceFormatted"] = best.get("formatted_final_price")
        yield rec
    if not keep and not weekends:
        yield error_record(label, "no_results", "No free-to-keep giveaway or Free Weekend is live right now.")


def _to_int(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- mode: featured

def _slug(name: str) -> str:
    return "_".join(str(name or "").lower().replace("-", " ").split()) or "unknown"


async def featured(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Storefront-curated deal events: Daily Deal, spotlights (Weekend Deal, Free Weekend,
    franchise / publisher sales) and the featured specials row."""
    label = f"featured:{opt.country}"
    if opt.include_usd:
        await FX.load(client)
    feat = parse_featured(await client.get_json(URL_FEATURED_CATEGORIES, {"cc": opt.country, "l": opt.language}))

    keys: list[tuple[str, int]] = []
    for it in feat["dailyDeals"] + feat["specials"]:
        if it.get("id"):
            keys.append(("app", int(it["id"])))
    targets = []
    for sp in feat["spotlights"]:
        kind, ident = spotlight_target(sp.get("url"))
        targets.append((sp, kind, ident))
        if kind in ("app", "sub", "bundle") and ident and ident.isdigit():
            keys.append(({"sub": "package"}.get(kind, kind), int(ident)))
    items = await fetch_store_items(client, keys, opt.country, opt) if opt.include_discount_details and keys else {}

    for it in feat["dailyDeals"]:
        rec = envelope(label, "S1-featured-dailydeal", "DAILY_DEAL", country=opt.country, dealCategory="daily_deal",
                       id=it.get("id"), appid=it.get("id"), name=it.get("name"), storeUrl=f"{STORE}/app/{it.get('id')}/",
                       discountPct=it.get("discount_percent"), purchasePackage=it.get("purchase_package"),
                       headerImage=it.get("header_image"))
        rec.update(_price_fields(it.get("final_price"), it.get("original_price"), it.get("currency"), opt))
        if opt.include_discount_details:
            rec.update(_detail_fields(items.get(("app", int(it["id"])))))
        yield rec

    sale_cache: dict[str, dict[str, Any] | None] = {}
    for n, (sp, kind, ident) in enumerate(targets, 1):
        rec = envelope(label, "S1-featured-spotlight", "SPOTLIGHT", country=opt.country, position=n,
                       dealCategory=_slug(sp.get("name")), spotlightName=sp.get("name"),
                       spotlightBody=sp.get("body"), url=sp.get("url"), targetType=kind, targetId=ident,
                       headerImage=sp.get("header_image"))
        if kind == "sale" and ident:
            if ident not in sale_cache:
                sale_cache[ident] = await _sale_meta(client, ident, opt)
            meta = sale_cache[ident]
            if meta:
                rec.update({k: v for k, v in meta.items() if k != "items"}, saleItemCount=len(meta["items"]))
                rec["hoursLeft"] = _hours_left(meta.get("saleEndsAtUnix"))
        elif kind in ("app", "sub", "bundle") and ident and ident.isdigit():
            item = items.get(({"sub": "package"}.get(kind, kind), int(ident)))
            best = (item or {}).get("best_purchase_option") or {}
            rec["name"] = (item or {}).get("name")
            rec["discountPct"] = best.get("discount_pct") or 0
            rec["finalPriceFormatted"] = best.get("formatted_final_price")
            rec["originalPriceFormatted"] = best.get("formatted_original_price")
            if opt.include_discount_details:
                rec.update(_detail_fields(item))
        yield rec

    for n, it in enumerate(feat["specials"], 1):
        rec = envelope(label, "S1-featured-specials", "FEATURED_SPECIAL", country=opt.country, position=n,
                       dealCategory="featured_special", id=it.get("id"), appid=it.get("id"), name=it.get("name"),
                       storeUrl=f"{STORE}/app/{it.get('id')}/", discountPct=it.get("discount_percent"),
                       discountExpiresAt=unix_to_iso(it.get("discount_expiration")),
                       platforms=[p for p, k in (("win", "windows_available"), ("mac", "mac_available"), ("linux", "linux_available")) if it.get(k)],
                       headerImage=it.get("header_image"))
        rec.update(_price_fields(it.get("final_price"), it.get("original_price"), it.get("currency"), opt))
        if opt.include_discount_details:
            rec.update(_detail_fields(items.get(("app", int(it["id"])))))
        else:
            rec["hoursLeft"] = _hours_left(it.get("discount_expiration"))
        yield rec


# --------------------------------------------------------------------------- mode: salePage

async def _sale_meta(client: SteamClient, slug: str, opt: Options) -> dict[str, Any] | None:
    try:
        page = await client.get_page(URL_SALE_PAGE + slug, {"cc": opt.country})
    except (Blocked, NotFound) as exc:
        log.warning("Sale page %s unavailable: %s", slug, exc)
        return None
    if "/sale/" not in page.url:
        return None  # ended / unknown sale -> homepage redirect (HTTP 200)
    try:
        meta = parse_sale_page(page.text)
    except UnexpectedShape as exc:
        log.warning("Sale page %s: %s", slug, exc)
        return None
    meta["saleUrl"] = f"{URL_SALE_PAGE}{slug}"
    return meta


_KEY_PREFIX = {"app": "App", "package": "Sub", "bundle": "Bundle"}


async def sale_page(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Every game / DLC / package / bundle listed on curated sale pages, priced."""
    if opt.include_usd:
        await FX.load(client)
    emitted = 0
    for ref in opt.sales:
        slug = parse_sale_ref(ref)
        if not slug:
            yield error_record(ref, "invalid_input", "Not a store.steampowered.com/sale/<name> URL or a sale name.")
            continue
        try:
            page = await client.get_page(URL_SALE_PAGE + slug, {"cc": opt.country})
        except (Blocked, NotFound) as exc:
            yield error_record(ref, "blocked" if isinstance(exc, Blocked) else "not_found", str(exc))
            continue
        if "/sale/" not in page.url:
            # Ended or unknown sale names redirect to the HOMEPAGE with HTTP 200
            # (925 KB, 200+ unrelated appids) - a silent-junk trap.
            yield error_record(ref, "not_found", f"Sale '{slug}' redirected to the store homepage: it has ended or never existed.")
            continue
        try:
            meta = parse_sale_page(page.text)
        except UnexpectedShape as exc:
            yield error_record(ref, "unexpected_shape", str(exc))
            continue
        sale_url = f"{URL_SALE_PAGE}{slug}"
        sale_fields = {k: v for k, v in meta.items() if k != "items"}
        summary = envelope(ref, "S1-sale-page", "SALE_PAGE", country=opt.country, saleUrl=sale_url, **sale_fields,
                           itemCount=len(meta["items"]), hoursLeft=_hours_left(meta.get("saleEndsAtUnix")))
        if not meta["items"]:
            summary["note"] = ("This sale page builds its lists dynamically (seasonal sales and Fests do). "
                               "Use the deals mode with a tag filter to list its discounts.")
        yield summary
        items = await fetch_store_items(client, [(i["itemType"], i["id"]) for i in meta["items"]], opt.country, opt)
        currency = await currency_for_country(client, [i["id"] for i in meta["items"] if i["itemType"] == "app"], opt.country)
        for i in meta["items"]:
            item = items.get((i["itemType"], i["id"]))
            best = (item or {}).get("best_purchase_option") or {}
            rec = envelope(ref, "S1-sale-page+getitems", "SALE_ITEM", country=opt.country, saleName=meta["saleName"],
                           saleUrl=sale_url, saleStartsAt=meta["saleStartsAt"], saleEndsAt=meta["saleEndsAt"],
                           itemKey=f"{_KEY_PREFIX[i['itemType']]}_{i['id']}",
                           itemType=i["itemType"], id=i["id"], capsuleType=i["capsuleType"], sectionIndex=i["sectionIndex"], sectionType=i["sectionType"],
                           name=(item or {}).get("name"),
                           storeUrl=f"{STORE}/{item['store_url_path']}" if item and item.get("store_url_path") else None,
                           discountPct=best.get("discount_pct") or 0,
                           finalPriceFormatted=best.get("formatted_final_price"),
                           originalPriceFormatted=best.get("formatted_original_price"))
            rec.update(_price_fields(_to_int(best.get("final_price_in_cents")), _to_int(best.get("original_price_in_cents")), currency, opt))
            rec.update(_detail_fields(item))
            yield rec
            emitted += 1
            if emitted >= opt.max_items:
                return


# --------------------------------------------------------------------------- mode: appPrices

async def app_prices(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Regional price + discount for each game in each country, normalised to USD."""
    resolved, errors = await resolve_apps(client, opt.apps, opt.countries[0])
    for e in errors:
        yield e
    if not resolved:
        return
    if opt.include_usd:
        await FX.load(client)
    appids = [a for _, a in resolved]
    label_of = {a: lab for lab, a in resolved}
    sem = asyncio.Semaphore(opt.concurrency)
    results: dict[str, dict[int, Any]] = {}
    details: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}

    async def country_prices(cc: str) -> None:
        out: dict[int, Any] = {}
        for i in range(0, len(appids), APPDETAILS_BATCH):
            chunk = appids[i:i + APPDETAILS_BATCH]
            async with sem:
                try:
                    data = await client.get_json(URL_APPDETAILS, {"appids": ",".join(map(str, chunk)), "filters": "price_overview", "cc": cc})
                except (Blocked, NotFound) as exc:
                    log.warning("appdetails %s failed: %s", cc, exc)
                    for a in chunk:
                        out[a] = exc
                    continue
            if not isinstance(data, dict):
                raise UnexpectedShape(f"appdetails returned {type(data).__name__}")
            for a in chunk:
                out[a] = data.get(str(a))
        results[cc] = out
        if opt.include_discount_details:
            details[cc] = await fetch_store_items(client, [("app", a) for a in appids], cc, opt)

    await asyncio.gather(*(country_prices(cc) for cc in opt.countries))

    missing = set()
    for a in appids:
        if all(isinstance(results[cc].get(a), dict) and results[cc][a].get("success") is False for cc in opt.countries):
            missing.add(a)
            yield error_record(label_of[a], "not_found", f"appid {a} has no Steam store page (appdetails success:false).")

    for a in appids:
        if a in missing:
            continue
        recs = []
        for cc in opt.countries:
            entry = results[cc].get(a)
            if isinstance(entry, Exception):
                yield error_record(label_of[a], "blocked", f"{cc}: {entry}")
                continue
            data = (entry or {}).get("data")
            po = data.get("price_overview") if isinstance(data, dict) else None
            rec = envelope(label_of[a], "S1-store-appdetails", "APP_PRICE", country=cc, appid=a, itemKey=f"App_{a}",
                           storeUrl=f"{STORE}/app/{a}/", priceAvailable=po is not None,
                           discountPct=(po or {}).get("discount_percent", 0),
                           finalPriceFormatted=(po or {}).get("final_formatted"),
                           originalPriceFormatted=(po or {}).get("initial_formatted"))
            # data == [] -> free-to-play, unreleased, or not sold in this country.
            rec.update(_price_fields((po or {}).get("final"), (po or {}).get("initial"), (po or {}).get("currency"), opt))
            if opt.include_discount_details:
                rec.update(_detail_fields(details.get(cc, {}).get(("app", a))))
                rec["name"] = rec.get("itemName")
            recs.append(rec)
        priced = [r for r in recs if r.get("finalPriceUsd") is not None]
        if opt.include_usd and len(priced) > 1:
            ordered = sorted(priced, key=lambda r: r["finalPriceUsd"])
            us = next((r for r in recs if r["country"] == "US" and r.get("finalPriceUsd")), None)
            for r in recs:
                r["cheapestCountry"] = ordered[0]["country"]
                r["cheapestPriceUsd"] = ordered[0]["finalPriceUsd"]
                if r in priced:
                    r["usdRank"] = ordered.index(r) + 1
                    r["vsUsPricePct"] = round((r["finalPriceUsd"] / us["finalPriceUsd"] - 1) * 100, 1) if us else None
        for r in recs:
            yield r


# --------------------------------------------------------------------------- mode: saleEvents

async def sale_events(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Steam's published calendar: seasonal sales, themed Fests and Next Fest."""
    page = await client.get_page(URL_EVENT_CALENDAR)
    events = parse_event_calendar(page.text)
    today = datetime.now(timezone.utc).date()
    for ev in events:
        start = date.fromisoformat(ev["startDate"]) if ev["startDate"] else None
        end = date.fromisoformat(ev["endDate"]) if ev["endDate"] else None
        if start is None:
            status = "tbd"
        elif today < start:
            status = "upcoming"
        elif end and today > end:
            status = "ended"
        else:
            status = "live"
        if status == "ended" and not opt.include_past_events:
            continue
        yield envelope("saleEvents", "S1-steamworks-upcoming-events", "SALE_EVENT", **ev, status=status,
                       daysUntilStart=(start - today).days if start else None,
                       durationDays=((end - start).days if start and end else None),
                       # Steam events switch over at 10:00 Pacific (17:00 UTC in summer, 18:00 in winter).
                       startTimeNote="Steam sales start and end at 10:00 Pacific Time",
                       calendarUrl=URL_EVENT_CALENDAR)


MODES = {
    "deals": deals,
    "featured": featured,
    "freebies": freebies,
    "appPrices": app_prices,
    "salePage": sale_page,
    "saleEvents": sale_events,
}
# Modes whose records carry a comparable price (change detection applies).
TRACKED_MODES = {"deals", "freebies", "appPrices", "salePage"}
