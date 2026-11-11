import asyncio
import json
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import Point2HomesClient
from src.constants import BASE_URL
from src.extractor import (
    UnexpectedShape,
    extract_error,
    extract_listing_detail,
    extract_search_page,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

VALID_PROPERTY_TYPES = ("Houses-For-Rent", "Apartments-For-Rent")
SEARCH_PAGE_SANITY_CAP = 400  # far beyond any realistic result set at 30 items/page


async def run_search(
    property_type: str,
    location: str,
    max_items: int,
    fetch_details: bool,
    max_concurrency: int,
    proxy_config,
) -> list[dict]:
    input_value = f"{property_type}:{location}"
    list_proxy_url = await proxy_config.new_url() if proxy_config else None
    list_client = Point2HomesClient(proxy_url=list_proxy_url)
    collected: list[dict] = []
    total = None
    try:
        base_url = f"{BASE_URL}/US/{property_type}/{location}.html"
        page = 1
        while len(collected) < max_items:
            params = {"page": page} if page > 1 else None
            r = await list_client.get(base_url, params=params)
            if r.status_code == 404:
                return [extract_error(input_value, "location_not_found", f"HTTP 404 for {base_url}")]
            if r.status_code != 200:
                return [extract_error(input_value, f"http_{r.status_code}", base_url)]
            if page == 1 and str(r.url).split("?", 1)[0] != base_url:
                # Point2Homes doesn't 404 on an unrecognized state/city slug -- it
                # 200s a *different* page (state-level or a generic default city)
                # via a silent redirect. Comparing the post-redirect URL back
                # against what we asked for is the only reliable signal that the
                # location itself doesn't exist; without this check a typo'd
                # location would silently return another city's listings.
                return [extract_error(
                    input_value, "location_not_found",
                    f"Redirected to {r.url} -- '{location}' is not a recognized Point2Homes location slug",
                )]

            items, total = extract_search_page(r.text)
            if not items:
                break
            collected.extend(items)
            if total is not None and len(collected) >= total:
                break
            page += 1
            if page > SEARCH_PAGE_SANITY_CAP:
                break
        collected = collected[:max_items]
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await list_client.close()

    if not collected:
        return []

    if not fetch_details:
        return [wrap({**it, "_gridTotal": total}, input_value, "S1-search-summary") for it in collected]

    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(collected)

    async def _enrich(idx: int, item: dict):
        async with sem:
            detail_url = (item.get("object") or {}).get("url")
            if not detail_url:
                results[idx] = extract_error(input_value, "missing_detail_url", json.dumps(item)[:300])
                return
            proxy_url = await proxy_config.new_url() if proxy_config else None
            client = Point2HomesClient(proxy_url=proxy_url)
            try:
                r = await client.get(detail_url)
                if r.status_code in (404, 410):
                    results[idx] = extract_error(detail_url, "listing_not_found", f"HTTP {r.status_code}")
                    return
                if r.status_code != 200:
                    results[idx] = extract_error(detail_url, f"http_{r.status_code}")
                    return
                record = extract_listing_detail(r.text, detail_url)
                if record is None:
                    results[idx] = extract_error(detail_url, "listing_not_found", "page 200'd but no RentAction JSON-LD block")
                    return
                results[idx] = wrap(record, input_value, "S2-detail")
            except (RuntimeError, ConnectionError, RequestException) as e:
                results[idx] = extract_error(detail_url, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_enrich(i, it) for i, it in enumerate(collected)))
    return [r for r in results if r is not None]


async def run_listing(url: str, proxy_url: str | None) -> dict:
    client = Point2HomesClient(proxy_url=proxy_url)
    try:
        r = await client.get(url)
        if r.status_code in (404, 410):
            # 410 is what Point2Homes actually returns for a removed/expired
            # listing URL (confirmed live) -- 404 kept as a defensive fallback.
            return extract_error(url, "listing_not_found", f"HTTP {r.status_code}")
        if r.status_code != 200:
            return extract_error(url, f"http_{r.status_code}")

        record = extract_listing_detail(r.text, url)
        if record is None:
            return extract_error(url, "listing_not_found", "page 200'd but no RentAction JSON-LD block")
        return wrap(record, url, "S2-detail")
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "listing")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        if mode == "search":
            property_type = input_data.get("propertyType", "Houses-For-Rent")
            if property_type not in VALID_PROPERTY_TYPES:
                raise input_error(f"Invalid propertyType: {property_type!r}. Must be one of {VALID_PROPERTY_TYPES}.")
            locations = list(input_data.get("locations") or [])
            if not locations:
                raise input_error("Provide 'locations' (e.g. [\"TX/Dallas\"]) when mode is 'search'.")
            max_items = int(input_data.get("maxItemsPerLocation", 60))
            fetch_details = bool(input_data.get("fetchDetails", True))

            for loc in locations:
                loc_clean = loc.strip().strip("/")
                if not loc_clean:
                    continue
                records = await run_search(property_type, loc_clean, max_items, fetch_details, max_concurrency, proxy_config)
                Actor.log.info(f"mode=search property_type={property_type} location={loc_clean}: {len(records)} record(s)")
                await Actor.push_data(records)
            return

        # mode == "listing"
        urls = list(input_data.get("listingUrls") or [])
        if not urls:
            raise input_error("Provide 'listingUrls' when mode is 'listing'.")
        seen: set[str] = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_listing(u: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_listing(u, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=listing: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_listing(u) for u in urls))
