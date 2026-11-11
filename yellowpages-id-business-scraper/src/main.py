"""Yellow Pages Indonesia scraper — six extraction modes over one HTTP client.

Why one actor instead of six
----------------------------
Every mode talks to the same Django app, through the same Cloudflare-avoiding
host choice, with the same pagination ceiling and the same record envelope. The
host decision alone (see constants.DATA_HOST) is the fragile part of this
scraper; splitting it across six actors would mean six copies to re-verify the
next time the zone config changes. Modes that emit different shapes are kept
apart by `recordType`, which the dataset schema exposes as separate views.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

from apify import Actor

from .client import BlockedError, UnexpectedShape, YellowPagesClient
from .constants import (
    CATEGORY_PATH,
    CITYMAP_PATH,
    CITY_PARAM,
    COUNTRY,
    DECOY_LOCATION_PARAM,
    DEFAULT_CONCURRENCY,
    MAX_PAGE,
    MAX_RECORDS_PER_QUERY,
    PAGE_PARAM,
    PRODUCT_SEARCH_PATH,
    PROVINCE_CODES,
    RECORD_BUSINESS,
    RECORD_COMPANY,
    RECORD_ERROR,
    RECORD_GEO,
    RECORD_INSIGHT,
    RECORD_PRODUCT,
    REGION_PARAM,
    SEARCH_PATH,
)
from . import parsers as P
from .input_errors import input_error

MODES = (
    "search_businesses",
    "category_businesses",
    "company_details",
    "search_products",
    "market_insights",
    "geo_directory",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """House envelope: traceability fields first, raw payload passed through."""
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now(),
        "recordType": record_type,
        **payload,
    }


def error_record(input_value: str, source: str, err: str, detail: str = "") -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now(),
        "recordType": RECORD_ERROR,
        "_error": err,
        "_errorDetail": detail[:500],
    }


# ---------------------------------------------------------------------------
# input handling
# ---------------------------------------------------------------------------
def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = []
        for v in value:
            if isinstance(v, dict):  # Apify requestListSources shape
                v = v.get("url") or v.get("value") or ""
            items.append(str(v))
    else:
        items = [str(value)]
    return [s.strip() for s in items if s and s.strip()]


def company_id_from(value: str) -> str | None:
    """Accept a full profile URL, a bare /profil-... path, or a numeric id."""
    value = value.strip()
    if value.isdigit():
        return value
    m = re.search(r"/profil-(\d+)-", value)
    return m.group(1) if m else None


def profile_path_from(value: str) -> str | None:
    """The site accepts any slug for a given id, so a bare id is enough."""
    value = value.strip()
    if value.isdigit():
        return f"/profil-{value}-x.html"
    if value.startswith("http"):
        parts = urlsplit(value)
        return parts.path
    if value.startswith("/"):
        return value
    return None


# ---------------------------------------------------------------------------
# paging
# ---------------------------------------------------------------------------
async def paged_listing(
    client: YellowPagesClient,
    path: str,
    params: dict[str, Any],
    limit: int,
    parse,
    log,
    has_results=P.listing_has_results,
) -> tuple[list[dict[str, Any]], str | None]:
    """Walk p=1..MAX_PAGE until the page yields nothing new or the cap is hit.

    Stops on *content*, never on status: p=MAX_PAGE+1 answers 200 with a fully
    rendered shell and zero cards.
    """
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    warning: str | None = None

    for page in range(1, MAX_PAGE + 1):
        page_params = dict(params)
        if page > 1:
            page_params[PAGE_PARAM] = page
        html, url = await client.get_text(path, page_params)
        if not html:
            break
        if not has_results(html):
            log.info(f"  page {page}: empty -> stop ({url})")
            break

        rows = parse(html)
        fresh = 0
        for row in rows:
            key = str(row.get("entryId") or row.get("productId") or row.get("name"))
            if key in seen:
                continue  # sponsored slots repeat on every page
            seen.add(key)
            collected.append(row)
            fresh += 1
            if len(collected) >= limit:
                break
        log.info(f"  page {page}: {len(rows)} parsed, {fresh} new, {len(collected)} total")
        if len(collected) >= limit:
            break
        if fresh == 0:
            break

    if len(collected) >= MAX_RECORDS_PER_QUERY:
        warning = (
            f"upstream_page_cap_reached: the backend serves at most {MAX_PAGE} pages "
            f"({MAX_RECORDS_PER_QUERY} rows) per query regardless of the advertised total. "
            f"Slice the query by region/city to go deeper."
        )
    return collected[:limit], warning


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------
async def run_search_businesses(client, log, cfg) -> None:
    for query in cfg["queries"]:
        params = {"ctr": COUNTRY, "q": query}
        if cfg["region"]:
            params[REGION_PARAM] = cfg["region"].lower()
        if cfg["city"]:
            params[CITY_PARAM] = cfg["city"].lower()
        log.info(f"search_businesses q={query!r} region={cfg['region']} city={cfg['city']}")
        try:
            rows, warn = await paged_listing(
                client, SEARCH_PATH, params, cfg["max_items"], P.parse_listing, log
            )
        except (BlockedError, UnexpectedShape) as exc:
            await Actor.push_data(error_record(query, "S1-listing-search", type(exc).__name__, str(exc)))
            continue
        await _push_businesses(rows, query, "S1-listing-search", warn, client, log, cfg)


async def run_category_businesses(client, log, cfg) -> None:
    for slug in cfg["queries"]:
        slug = slug.strip("/").replace(" ", "-").lower()
        path = CATEGORY_PATH.format(slug=slug)
        if cfg["city"]:
            path += "/" + cfg["city"].replace(" ", "-").title()
        log.info(f"category_businesses slug={slug} city={cfg['city']} -> {path}")
        try:
            rows, warn = await paged_listing(
                client, path, {}, cfg["max_items"], P.parse_listing, log
            )
        except (BlockedError, UnexpectedShape) as exc:
            await Actor.push_data(error_record(slug, "S2-category-page", type(exc).__name__, str(exc)))
            continue
        if not rows:
            await Actor.push_data(error_record(
                slug, "S2-category-page", "no_results",
                "category slug returned no entries; it may not exist on this site",
            ))
            continue
        await _push_businesses(rows, slug, "S2-category-page", warn, client, log, cfg)


async def _push_businesses(rows, input_value, source, warning, client, log, cfg) -> None:
    if cfg["enrich"]:
        rows = await _enrich(rows, client, log, cfg)
    for row in rows:
        rec = envelope(input_value, source, RECORD_BUSINESS, row)
        if warning:
            rec["_warning"] = warning
        await Actor.push_data(rec)
    log.info(f"  pushed {len(rows)} business records for {input_value!r}")


async def _enrich(rows, client, log, cfg):
    """Fetch each company's profile page and merge the extra fields in.

    Profile pages carry founding year, legal form, phone labels and categories
    but no coordinates, so listing geo is kept rather than overwritten.
    """
    targets = [r for r in rows if r.get("companyId")]
    log.info(f"  enriching {len(targets)} company profiles (concurrency {cfg['concurrency']})")
    sem = asyncio.Semaphore(cfg["concurrency"])

    async def one(row):
        async with sem:
            path = f"/profil-{row['companyId']}-x.html"
            try:
                html, url = await client.get_text(path, None)
                if not html:
                    return
                detail = P.parse_profile(html, url)
            except (BlockedError, UnexpectedShape) as exc:
                log.warning(f"  enrich failed for {row['companyId']}: {exc}")
                return
            for key, value in detail.items():
                # Keep listing coordinates: profile pages publish none.
                # Keep the listing's URLs too — they carry the real slug, while
                # the fetch used a synthetic "-x" slug the site accepts as an alias.
                if key in ("geo", "detailUrl", "yellowpagesUrl") and row.get(key):
                    continue
                # Never let a blank detail field erase a good listing value.
                if value not in (None, [], {}, ""):
                    row[key] = value
            row["_enriched"] = True

    await asyncio.gather(*(one(r) for r in targets))
    return rows


async def run_company_details(client, log, cfg) -> None:
    sem = asyncio.Semaphore(cfg["concurrency"])

    async def one(value: str):
        async with sem:
            path = profile_path_from(value)
            if not path:
                await Actor.push_data(error_record(
                    value, "S3-profile", "unresolvable_input",
                    "expected a /profil-<id>-<slug>.html URL or a numeric company id",
                ))
                return
            try:
                html, url = await client.get_text(path, None)
                if not html:
                    await Actor.push_data(error_record(value, "S3-profile", "not_found", path))
                    return
                detail = P.parse_profile(html, url)
            except (BlockedError, UnexpectedShape) as exc:
                await Actor.push_data(error_record(value, "S3-profile", type(exc).__name__, str(exc)))
                return
            await Actor.push_data(envelope(value, "S3-profile", RECORD_COMPANY, detail))

    log.info(f"company_details: {len(cfg['company_urls'])} targets")
    await asyncio.gather(*(one(v) for v in cfg["company_urls"]))


async def run_search_products(client, log, cfg) -> None:
    for query in cfg["queries"]:
        log.info(f"search_products q={query!r}")
        try:
            rows, warn = await paged_listing(
                client, PRODUCT_SEARCH_PATH, {"ctr": COUNTRY, "q": query},
                cfg["max_items"], P.parse_products, log,
                has_results=P.products_have_results,
            )
        except (BlockedError, UnexpectedShape) as exc:
            await Actor.push_data(error_record(query, "S4-product-search", type(exc).__name__, str(exc)))
            continue
        for row in rows:
            rec = envelope(query, "S4-product-search", RECORD_PRODUCT, row)
            if warn:
                rec["_warning"] = warn
            await Actor.push_data(rec)
        log.info(f"  pushed {len(rows)} product records")


async def run_market_insights(client, log, cfg) -> None:
    """Facet counts per region/city — market density for a keyword.

    One request answers 'how many bank listings exist in each province', which
    is the cheapest demand signal the site exposes.
    """
    for query in cfg["queries"]:
        log.info(f"market_insights q={query!r}")
        try:
            html, url = await client.get_text(SEARCH_PATH, {"ctr": COUNTRY, "q": query})
        except BlockedError as exc:
            await Actor.push_data(error_record(query, "S5-facets", "BlockedError", str(exc)))
            continue
        facets = P.parse_facets(html)
        payload = {
            "keyword": query,
            "advertisedTotal": P.parse_result_total(html),
            "reachableTotal": MAX_RECORDS_PER_QUERY,
            "regions": facets["regions"],
            "cities": facets["cities"],
            "similarKeywords": facets["similarKeywords"],
            "sourceUrl": url,
            "yellowpagesUrl": P.canonical_url(url),
        }
        rec = envelope(query, "S5-facets", RECORD_INSIGHT, payload)
        if not facets["regions"] and not facets["cities"]:
            rec["_warning"] = "no_facets_returned: keyword may have too few listings to bucket"
        await Actor.push_data(rec)
        log.info(f"  {len(facets['regions'])} regions, {len(facets['cities'])} cities")


async def run_geo_directory(client, log, cfg) -> None:
    codes = cfg["province_codes"] or list(PROVINCE_CODES)
    sem = asyncio.Semaphore(cfg["concurrency"])

    async def one(code: str):
        async with sem:
            code = str(code).zfill(2)
            try:
                html, url = await client.get_text(CITYMAP_PATH.format(code=code), None)
            except BlockedError as exc:
                await Actor.push_data(error_record(code, "S6-citymap", "BlockedError", str(exc)))
                return
            if not html:
                await Actor.push_data(error_record(code, "S6-citymap", "not_found", code))
                return
            cities = P.parse_citymap(html)
            # Unused codes answer 200 with an "Aceh"-titled shell and no cities.
            # Report that as an error rather than pushing an empty province.
            if not cities and code != "01":
                await Actor.push_data(error_record(
                    code, "S6-citymap", "hollow_response",
                    f"province code {code} renders a 200 page with zero cities — "
                    f"it is not one of the {len(PROVINCE_CODES)} codes this site uses",
                ))
                return
            payload = {
                "provinceCode": code,
                "provinceName": PROVINCE_CODES.get(code),
                "cityCount": len(cities),
                "cities": cities,
                "sourceUrl": url,
                "yellowpagesUrl": P.canonical_url(url),
            }
            await Actor.push_data(envelope(code, "S6-citymap", RECORD_GEO, payload))
            log.info(f"  province {code} ({PROVINCE_CODES.get(code)}): {len(cities)} cities")

    log.info(f"geo_directory: {len(codes)} provinces")
    await asyncio.gather(*(one(c) for c in codes))


async def _maybe_proxy_url(proxy_input: Any, log) -> str | None:
    """Resolve a proxy URL, or None to go direct.

    Recon found no IP-based blocking on this target — the same address gets 200
    on every path that is not behind the zone's path rule — so a proxy is a
    genuine opt-in. Calling create_proxy_configuration unconditionally makes the
    SDK demand an Apify proxy password and kills runs that never wanted one.
    """
    if not isinstance(proxy_input, dict):
        return None
    if not (proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls")):
        return None
    try:
        config = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
    except Exception as exc:
        # A misconfigured proxy must not fail a run that works fine direct.
        log.warning(f"Proxy configuration failed ({exc!r}) — continuing without a proxy.")
        return None
    return await config.new_url() if config else None


RUNNERS = {
    "search_businesses": run_search_businesses,
    "category_businesses": run_category_businesses,
    "company_details": run_company_details,
    "search_products": run_search_products,
    "market_insights": run_market_insights,
    "geo_directory": run_geo_directory,
}


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        mode = (actor_input.get("mode") or "search_businesses").strip()
        if mode not in MODES:
            raise input_error(f"unknown mode {mode!r}; expected one of {', '.join(MODES)}")

        cfg = {
            "queries": _as_list(actor_input.get("queries")),
            "company_urls": _as_list(actor_input.get("companyUrls")),
            "province_codes": _as_list(actor_input.get("provinceCodes")),
            "region": (actor_input.get("region") or "").strip(),
            "city": (actor_input.get("city") or "").strip(),
            "max_items": int(actor_input.get("maxItemsPerQuery") or MAX_RECORDS_PER_QUERY),
            "enrich": bool(actor_input.get("enrichWithDetails")),
            "concurrency": max(1, min(int(actor_input.get("maxConcurrency") or DEFAULT_CONCURRENCY), 10)),
        }

        if DECOY_LOCATION_PARAM in {k.lower() for k in actor_input}:
            log.warning(
                "Ignoring the free-text location input: the site's `l=` parameter is a decoy "
                "that always returns zero results. Use `region` / `city` instead."
            )

        if mode in ("search_businesses", "category_businesses", "search_products", "market_insights") \
                and not cfg["queries"]:
            raise input_error(f"mode {mode!r} requires at least one entry in `queries`")
        if mode == "company_details" and not cfg["company_urls"]:
            raise input_error("mode 'company_details' requires at least one entry in `companyUrls`")

        if cfg["max_items"] > MAX_RECORDS_PER_QUERY:
            log.warning(
                f"maxItemsPerQuery={cfg['max_items']} exceeds the upstream ceiling of "
                f"{MAX_RECORDS_PER_QUERY}; the run will stop there. Split the query by "
                f"region/city to collect more."
            )

        proxy_url = await _maybe_proxy_url(actor_input.get("proxyConfiguration"), log)
        log.info(f"mode={mode} proxy={'on' if proxy_url else 'off'}")

        async with YellowPagesClient(proxy_url=proxy_url, log=log) as client:
            await RUNNERS[mode](client, log, cfg)
            log.info(f"done (data host: {client.host})")
