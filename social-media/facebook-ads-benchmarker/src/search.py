"""Ad Library search and pagination, shared with the Ad Library scraper actor.

The benchmarker is only as good as its sample, so it uses the same fetch path as
the full scraper rather than a cut-down one: challenge solving, the 30
server-rendered ads, then Facebook's own pagination query for the rest.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from apify import Actor

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders
from src.parser import matches_filters, parse_graphql, parse_page

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
