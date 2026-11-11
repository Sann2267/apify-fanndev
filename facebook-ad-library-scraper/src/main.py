"""Facebook Ad Library Full Scraper -- Apify actor entry point."""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from typing import Any

from apify import Actor

from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession, harvest_preloaders
from src.parser import matches_filters, parse_graphql, parse_page, summarise
from src.runtime import envelope, error_record, resolve_proxy, utc_now_iso, write_exports
from src.input_errors import input_error

SOURCE = "ad-library"
BASE = "https://www.facebook.com/ads/library/"
PAGINATION_QUERY = "AdLibrarySearchPaginationQuery"

# The pagination query takes exactly these variables. They are copied out of the
# variables Facebook itself preloaded the page with, so a filter the UI applied
# carries over to page two without being re-encoded by hand.
PAGINATION_VARS = [
    "activeStatus", "adType", "bylines", "collationToken", "contentLanguages",
    "countries", "excludedIDs", "isTargetedCountry", "location", "mediaType",
    "multiCountryFilterMode", "pageIDs", "potentialReachInput",
    "publisherPlatforms", "queryString", "regions", "searchType", "sessionID",
    "sortData", "source", "startDate", "v", "viewAllPageID",
]

PAGE_ID_IN_URL = re.compile(r"view_all_page_id=(\d+)")
NUMERIC = re.compile(r"^\d{5,}$")


def page_id_from(value: str) -> str | None:
    """Accept a numeric page id, an Ad Library URL, or a page URL carrying one."""
    value = (value or "").strip()
    if not value:
        return None
    if NUMERIC.match(value):
        return value
    match = PAGE_ID_IN_URL.search(value)
    return match.group(1) if match else None


def build_url(query: dict) -> str:
    """Compose one Ad Library search URL.

    Facebook accepts a single `country` in the URL even though the underlying
    query takes a list, so multiple countries are run as separate searches. That
    is not a limitation worth hiding: a per-country run is also what a buyer
    comparing markets actually wants in the dataset.
    """
    params: list[tuple[str, str]] = [
        ("active_status", query["activeStatus"]),
        ("ad_type", query["adType"]),
        ("country", query["country"]),
        ("media_type", query["mediaType"]),
    ]
    if query.get("pageId"):
        params.append(("view_all_page_id", query["pageId"]))
        params.append(("search_type", "page"))
    else:
        params.append(("q", query["term"]))
        params.append(("search_type", query["searchType"]))
    for index, platform in enumerate(query.get("publisherPlatforms") or []):
        params.append((f"publisher_platforms[{index}]", platform))
    for index, language in enumerate(query.get("contentLanguages") or []):
        params.append((f"content_languages[{index}]", language))
    if query.get("startDateMin"):
        params.append(("start_date[min]", query["startDateMin"]))
    if query.get("startDateMax"):
        params.append(("start_date[max]", query["startDateMax"]))
    return BASE + "?" + urllib.parse.urlencode(params)


def read_queries(actor_input: dict) -> list[dict]:
    """Expand the input into one search per (target x country)."""
    countries = [c.strip().upper() for c in (actor_input.get("countries") or ["US"]) if c.strip()]
    countries = list(dict.fromkeys(countries)) or ["US"]

    common = {
        "activeStatus": actor_input.get("activeStatus") or "active",
        "adType": actor_input.get("adType") or "all",
        "mediaType": actor_input.get("mediaType") or "all",
        "searchType": actor_input.get("searchType") or "keyword_unordered",
        "publisherPlatforms": actor_input.get("publisherPlatforms") or [],
        "contentLanguages": actor_input.get("contentLanguages") or [],
        "startDateMin": (actor_input.get("startDateFrom") or "").strip() or None,
        "startDateMax": (actor_input.get("startDateTo") or "").strip() or None,
    }

    targets: list[dict] = []
    for term in actor_input.get("searchTerms") or []:
        term = str(term).strip()
        if term:
            targets.append({"term": term, "pageId": None, "label": f"keyword:{term}"})

    for raw in actor_input.get("advertisers") or []:
        value = raw.get("url") if isinstance(raw, dict) else raw
        page_id = page_id_from(str(value or ""))
        if page_id:
            targets.append({"term": None, "pageId": page_id, "label": f"page:{page_id}"})
        else:
            Actor.log.warning(
                f"Skipping advertiser {value!r}: the Ad Library addresses advertisers "
                "by numeric page id, and none could be read from this value. Open the "
                "advertiser in the Ad Library and copy the view_all_page_id from the URL."
            )

    queries = []
    for target in targets:
        for country in countries:
            queries.append({**common, **target, "country": country})
    return queries


async def collect(
    session: FacebookSession,
    query: dict,
    max_ads: int,
    filters: dict,
) -> tuple[list[dict], dict]:
    """Fetch one search: the rendered first page, then GraphQL for the rest."""
    url = build_url(query)
    html = await session.get_html(url)
    first = parse_page(html)

    kept: list[dict] = []
    seen: set[str] = set()
    meta = {
        "searchUrl": url,
        "totalMatchingAds": first.get("totalMatchingAds"),
        "pagesFetched": 1,
        "paginated": False,
    }

    def absorb(batch: list[dict]) -> bool:
        """Add a page of ads. False once the cap is reached."""
        for ad in batch:
            key = ad.get("adArchiveId")
            if not key or key in seen:
                continue
            seen.add(key)
            if matches_filters(ad, filters):
                kept.append(ad)
            if len(seen) >= max_ads:
                return False
        return True

    more = absorb(first["ads"])
    cursor = first.get("cursor")
    has_next = first.get("hasNextPage")

    if not more or not has_next or not cursor:
        return kept, meta

    doc_id = await session.bundle_doc_id(html, PAGINATION_QUERY)
    if not doc_id:
        # The rendered page is still a complete, honest answer -- it is simply
        # the first 30 ads. Saying so beats failing the whole search.
        meta["paginationUnavailable"] = True
        return kept, meta

    preloaded = harvest_preloaders(html)
    base_vars: dict[str, Any] = {}
    for _, (_, variables) in preloaded.items():
        if "queryString" in variables or "viewAllPageID" in variables:
            base_vars = variables
            break
    if not base_vars:
        meta["paginationUnavailable"] = True
        return kept, meta

    variables = {key: base_vars.get(key) for key in PAGINATION_VARS}
    variables["first"] = 30
    meta["paginated"] = True

    while more and has_next and cursor and len(seen) < max_ads:
        variables["cursor"] = cursor
        try:
            payload = await session.graphql(
                html, PAGINATION_QUERY, doc_id, variables, referer=url
            )
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        batch = parse_graphql(payload)
        if not batch["ads"]:
            # A page that returns zero ads is either the end of the result set or
            # a refusal wearing an HTTP 200. Facebook puts the difference in the
            # reply's `errors` array, so it is surfaced rather than swallowed --
            # otherwise a blocked pagination looks exactly like "no more ads".
            errors = payload.get("errors") or []
            if errors:
                detail = errors[0].get("message") if isinstance(errors[0], dict) else str(errors[0])
                meta["paginationStoppedBy"] = f"GraphQL error: {detail}"
                Actor.log.warning(
                    f"Pagination stopped after {meta['pagesFetched']} page(s): {detail}"
                )
            else:
                meta["paginationEnded"] = "empty page with no error -- end of results"
            break
        meta["pagesFetched"] += 1
        more = absorb(batch["ads"])
        cursor = batch.get("cursor")
        has_next = batch.get("hasNextPage")

    return kept, meta


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        queries = read_queries(actor_input)
        if not queries:
            raise input_error(
                "Nothing to search. Supply searchTerms (e.g. ['running shoes']) "
                "or advertisers (Ad Library URLs, or numeric page ids)."
            )

        max_ads = max(1, min(int(actor_input.get("maxAdsPerQuery", 60)), 5000))
        filters = {
            "onlyActive": bool(actor_input.get("onlyActive")),
            "onlyWithVideo": bool(actor_input.get("onlyWithVideo")),
            "minRunningDays": actor_input.get("minRunningDays"),
            "adTextContains": actor_input.get("adTextContains"),
        }
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(
            f"{len(queries)} search(es), up to {max_ads} ad(s) each. "
            "The Ad Library answers the first request with a 403 challenge; "
            "it is solved once per session."
        )

        all_ads: list[dict] = []
        records: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for query in queries:
                label = f"{query['label']} @ {query['country']}"
                try:
                    ads, meta = await collect(session, query, max_ads, filters)
                except BlockedError as exc:
                    failures += 1
                    record = error_record(SOURCE, label, "fetch_failed", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                except Exception as exc:  # one bad search must not end the run
                    failures += 1
                    record = error_record(
                        SOURCE, label, "unexpected_error", f"{type(exc).__name__}: {exc}"
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                if meta.get("paginationUnavailable"):
                    Actor.log.warning(
                        f"{label}: kept the {len(ads)} server-rendered ad(s); Facebook's "
                        "pagination query id could not be read from the page bundles this run."
                    )
                Actor.log.info(
                    f"{label}: {len(ads)} ad(s) kept from {meta['pagesFetched']} page(s)"
                    + (
                        f" of ~{meta['totalMatchingAds']:,} matching"
                        if isinstance(meta.get("totalMatchingAds"), int)
                        else ""
                    )
                )

                for ad in ads:
                    record = {
                        **envelope(SOURCE, label, "AD"),
                        **ad,
                        "searchCountry": query["country"],
                        "searchTerm": query.get("term"),
                        "searchPageId": query.get("pageId"),
                        "searchUrl": meta["searchUrl"],
                        "totalMatchingAds": meta.get("totalMatchingAds"),
                    }
                    records.append(record)
                    all_ads.append(record)
                    await Actor.push_data(record)

        if emit_summary and all_ads:
            summary = {
                **envelope(SOURCE, f"{len(queries)} search(es)", "RUN_SUMMARY"),
                **summarise(all_ads),
                "searchesRun": len(queries),
                "failedSearches": failures,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {summary['adsCollected']} ad(s), "
                f"{summary['activeAds']} active, "
                f"{summary['distinctAdvertisers']} advertiser(s), "
                f"median run {summary['medianRunningDays']} day(s)"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(all_ads)} ad(s) | {failures} failed search(es)")
        if failures and not all_ads:
            raise RuntimeError(
                "Every search failed and nothing was collected -- see the ERROR records."
            )


__all__ = ["main", "utc_now_iso"]
