"""Facebook Marketplace Leads Scraper -- Apify actor entry point."""

from __future__ import annotations

import re

from apify import Actor

from src.exporters import BUILDERS
from src.fbcore import TLS_LADDER, BlockedError, FacebookSession
from src.marketplace import FeedUnavailable, collect, enrich
from src.parser import item_id, matches_filters, summarise
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.input_errors import input_error

SOURCE = "marketplace"
NUMERIC_CITY = re.compile(r"^\d+$")


def read_queries(actor_input: dict) -> list[dict]:
    """One query per (city x category) and per (city x search term)."""
    cities = [str(c).strip().strip("/") for c in (actor_input.get("cities") or []) if str(c).strip()]
    cities = list(dict.fromkeys(cities))

    rejected = [c for c in cities if NUMERIC_CITY.match(c)]
    for city in rejected:
        Actor.log.warning(
            f"Ignoring city {city!r}: Marketplace is addressed by city SLUG, not by "
            "numeric location id. A numeric id returns HTTP 200 and a full page of "
            "listings from Facebook's default location instead of yours, which is "
            "worse than an error. Use the slug from the Marketplace URL, e.g. "
            "'nyc', 'jakarta', 'london'."
        )
    cities = [c for c in cities if not NUMERIC_CITY.match(c)]

    categories = [str(c).strip().strip("/") for c in (actor_input.get("categories") or [])
                  if str(c).strip()]
    searches = [str(s).strip() for s in (actor_input.get("searchQueries") or []) if str(s).strip()]

    common = {
        "minPrice": actor_input.get("minPrice"),
        "maxPrice": actor_input.get("maxPrice"),
        "sortBy": actor_input.get("sortBy") or None,
        "radiusKm": actor_input.get("radiusKm"),
    }

    queries: list[dict] = []
    targets = cities or [""]
    for city in targets:
        for category in categories:
            queries.append({**common, "city": city, "category": category, "search": None,
                            "label": f"{city or 'default'} / {category}"})
        for search in searches:
            queries.append({**common, "city": city, "category": None, "search": search,
                            "label": f"{city or 'default'} / search:{search}"})
    return queries


def read_items(actor_input: dict) -> list[str]:
    out = []
    for raw in actor_input.get("listingUrls") or []:
        value = raw.get("url") if isinstance(raw, dict) else raw
        found = item_id(str(value or ""))
        if found:
            out.append(found)
        else:
            Actor.log.warning(f"Skipping {value!r}: no Marketplace item id in it.")
    return list(dict.fromkeys(out))


FEED_ATTEMPTS = 3


async def collect_with_rotation(session, query: dict, max_listings: int):
    """`collect`, retried on a fresh connection when the feed comes back empty.

    Facebook decides the payload tier per exit IP: some residential addresses get
    the REDUCED page (HTTP 200, no feed), which used to fail the query outright.
    The proxy URL carries no session id, so rebuilding the session opens a new
    connection through a new exit IP; the TLS profile is rotated along with it.
    """
    for attempt in range(1, FEED_ATTEMPTS + 1):
        try:
            return await collect(session, query, max_listings, log=Actor.log)
        except (FeedUnavailable, BlockedError) as exc:
            if attempt == FEED_ATTEMPTS:
                raise
            nxt = TLS_LADDER[attempt % len(TLS_LADDER)]
            Actor.log.warning(
                f"{query['label']}: {exc} (attempt {attempt}/{FEED_ATTEMPTS}); "
                f"retrying on a new connection with {nxt}."
            )
            await session.reset(nxt)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        queries = read_queries(actor_input)
        items = read_items(actor_input)
        if not queries and not items:
            raise input_error(
                "Nothing to scrape. Supply cities plus categories or searchQueries, "
                "or listingUrls for specific items. City slugs look like 'nyc', "
                "'jakarta', 'london' - the segment in the Marketplace URL."
            )

        max_listings = max(1, min(int(actor_input.get("maxListingsPerQuery", 48)), 2000))
        fetch_details = bool(actor_input.get("fetchDetails"))
        max_details = max(1, min(int(actor_input.get("maxDetailFetches", 50)), 1000))
        filters = {
            "excludeSold": bool(actor_input.get("excludeSold", True)),
            "titleContains": actor_input.get("titleContains"),
            "minPrice": actor_input.get("minPrice"),
            "maxPrice": actor_input.get("maxPrice"),
            "maxAgeDays": actor_input.get("maxAgeDays"),
        }
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(
            f"{len(queries)} feed query/queries and {len(items)} direct listing(s)."
        )
        if actor_input.get("maxAgeDays") is not None:
            Actor.log.info(
                "Recency is filtered locally against each listing's creation_time: "
                "Facebook's own daysSinceListed URL parameter is accepted and ignored."
            )

        records: list[dict] = []
        kept: list[dict] = []
        failures = 0
        details_done = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for query in queries:
                try:
                    listings, meta = await collect_with_rotation(session, query, max_listings)
                except (FeedUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, query["label"], "feed_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                except Exception as exc:
                    failures += 1
                    record = error_record(
                        SOURCE, query["label"], "unexpected_error",
                        f"{type(exc).__name__}: {exc}",
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                if meta.get("paginationUnavailable"):
                    Actor.log.warning(
                        f"{query['label']}: kept the {len(listings)} rendered listing(s); "
                        "Facebook's pagination query could not be read this run."
                    )

                selected = [l for l in listings if matches_filters(l, filters)]
                Actor.log.info(
                    f"{query['label']}: {len(selected)} listing(s) kept of {len(listings)} "
                    f"in {meta['requestsMade']} request(s)"
                )

                for listing in selected:
                    if fetch_details and details_done < max_details:
                        listing.update(await enrich(session, listing))
                        details_done += 1
                    record = {
                        **envelope(SOURCE, query["label"], "LISTING"),
                        **listing,
                        "queryCity": query.get("city") or None,
                        "queryCategory": query.get("category"),
                        "querySearch": query.get("search"),
                        "searchUrl": meta["searchUrl"],
                    }
                    records.append(record)
                    kept.append(listing)
                    await Actor.push_data(record)

            for listing_id in items:
                stub = {
                    "listingId": listing_id,
                    "listingUrl": f"https://www.facebook.com/marketplace/item/{listing_id}/",
                }
                detail = await enrich(session, stub)
                if not detail.get("detailFound"):
                    failures += 1
                    record = error_record(
                        SOURCE, listing_id, "listing_unavailable",
                        "Facebook served the listing page but it carried no data for "
                        "this id. The listing was probably removed or sold.",
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                record = {
                    **envelope(SOURCE, listing_id, "LISTING"),
                    **stub,
                    **detail,
                }
                records.append(record)
                kept.append(record)
                await Actor.push_data(record)

        if emit_summary and kept:
            stats = summarise(kept)
            summary = {
                **envelope(SOURCE, f"{len(queries)} query/queries", "RUN_SUMMARY"),
                **stats,
                "queriesRun": len(queries),
                "directListings": len(items),
                "failedQueries": failures,
                "detailsFetched": details_done,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {stats['listingsCollected']} listing(s) across "
                f"{stats['distinctCities']} city/cities | prices "
                f"{stats['minPrice']} / {stats['medianPrice']} / {stats['maxPrice']} | "
                f"seller names available on {stats['sellerNamesAvailable']}"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept)} listing(s) | {failures} failure(s)")
        if failures and not kept:
            raise RuntimeError(
                "Every query failed and nothing was collected -- see the ERROR records."
            )
