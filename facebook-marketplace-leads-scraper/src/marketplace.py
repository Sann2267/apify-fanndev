"""Building Marketplace URLs and paging through a feed.

Two things about this surface are worth stating plainly, because both are easy
to get silently wrong:

**Location is addressed by city slug, not by id.**
`/marketplace/109571519060768/vehicles` returns HTTP 200 and a full page of
listings -- from Menlo Park, California, the same default feed a request with no
location at all receives. The numeric id is accepted and ignored.
`/marketplace/jakarta/vehicles` and `/marketplace/nyc/vehicles` return genuinely
local results (Jakarta, then New York/New Jersey). So this actor takes city
slugs, and rejects numeric ids with a message rather than handing back the wrong
city's listings as if they were right.

**Some URL filters work and one does not.**
Measured on the same feed, 24 listings each:

| Parameter | Effect |
| --- | --- |
| `minPrice` / `maxPrice` | honoured -- price range moved from $80-$37,485 to $20,000-$39,000 |
| `sortBy=creation_time_descend` | honoured -- different result set |
| `daysSinceListed` | **ignored** -- byte-for-byte the same listings as without it |

`daysSinceListed` is therefore not exposed. Recency is filtered locally against
each listing's own `creation_time`, which is a real number Facebook publishes.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders
from src.parser import parse_detail, parse_feed, parse_feed_html

BASE = "https://www.facebook.com/marketplace/"
CATEGORY_QUERY = "CometMarketplaceCategoryContentContainerQuery"
SEARCH_QUERY = "CometMarketplaceSearchRootQuery"
CATEGORY_PAGINATION = "CometMarketplaceCategoryContentPaginationQuery"
SEARCH_PAGINATION = "CometMarketplaceSearchContentPaginationQuery"

BATCH = 24


class FeedUnavailable(RuntimeError):
    """Facebook served no listings for this query."""


def build_url(query: dict) -> str:
    """Compose one Marketplace URL from a city slug plus a category or a search."""
    city = (query.get("city") or "").strip().strip("/")
    search = (query.get("search") or "").strip()
    category = (query.get("category") or "").strip().strip("/")

    if search:
        path = f"{city}/search/" if city else "search/"
    elif city:
        path = f"{city}/{category}" if category else city
    else:
        path = f"category/{category}" if category else ""

    params: list[tuple[str, str]] = []
    if search:
        params.append(("query", search))
    if query.get("minPrice") is not None:
        params.append(("minPrice", str(int(query["minPrice"]))))
    if query.get("maxPrice") is not None:
        params.append(("maxPrice", str(int(query["maxPrice"]))))
    if query.get("sortBy"):
        params.append(("sortBy", query["sortBy"]))
    if query.get("radiusKm") is not None:
        params.append(("radius", str(int(query["radiusKm"]) * 1000)))

    url = BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return url


async def collect(
    session: FacebookSession,
    query: dict,
    max_listings: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    """Fetch one Marketplace query: the rendered page, then GraphQL for the rest."""
    url = build_url(query)
    html = await session.get_html(url)
    listings, cursor = parse_feed_html(html)
    meta = {"searchUrl": url, "requestsMade": 1, "paginated": False}

    if not listings:
        raise FeedUnavailable(
            "Facebook returned no listings for this query. Check the city slug "
            "(it is the one in the Marketplace URL, e.g. 'nyc', 'jakarta', "
            "'london') and the category name."
        )

    seen = {l["listingId"] or l["title"] for l in listings}
    if len(listings) >= max_listings or not cursor:
        return listings[:max_listings], meta

    is_search = bool(query.get("search"))
    root_query = SEARCH_QUERY if is_search else CATEGORY_QUERY
    pagination_query = SEARCH_PAGINATION if is_search else CATEGORY_PAGINATION

    preloaders = harvest_preloaders(html)
    if root_query not in preloaders:
        meta["paginationUnavailable"] = True
        return listings[:max_listings], meta
    _, base_vars = preloaders[root_query]

    doc_id = await session.bundle_doc_id(html, pagination_query)
    if not doc_id:
        meta["paginationUnavailable"] = True
        return listings[:max_listings], meta

    meta["paginated"] = True
    while len(listings) < max_listings and cursor:
        variables = dict(base_vars)
        variables["cursor"] = cursor
        variables["count"] = BATCH
        try:
            payload = await session.graphql(
                html, pagination_query, doc_id, variables, referer=url
            )
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        meta["requestsMade"] += 1

        batch, cursor = parse_feed(payload)
        fresh = [l for l in batch if (l["listingId"] or l["title"]) not in seen]
        if not fresh:
            break
        for listing in fresh:
            seen.add(listing["listingId"] or listing["title"])
        listings.extend(fresh)
        if log:
            log.info(f"  +{len(fresh)} listing(s) (running total {len(listings)})")

    return listings[:max_listings], meta


async def enrich(session: FacebookSession, listing: dict) -> dict:
    """Add the listing page's own fields: description, coordinates, specs."""
    listing_id = listing.get("listingId")
    if not listing_id:
        return {}
    url = listing.get("listingUrl")
    try:
        html = await session.get_html(url)
    except BlockedError:
        return {"detailFound": False}
    return parse_detail(html, listing_id)
