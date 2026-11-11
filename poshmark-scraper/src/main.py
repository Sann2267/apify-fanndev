import asyncio
import logging
from urllib.parse import quote

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import PoshmarkClient
from src.constants import BASE_URL, SORT_BY_VALUES
from src.extractor import (
    UnexpectedShape,
    extract_browse_page,
    extract_error,
    extract_initial_state,
    extract_listing,
    extract_seller,
    wrap_browse_items,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_browse(browse_by: str, value: str, sort_by: str | None, max_items: int, proxy_url: str | None) -> list[dict]:
    client = PoshmarkClient(proxy_url=proxy_url)
    try:
        encoded_value = quote(value, safe="-")
        path = f"/brand/{encoded_value}" if browse_by == "brand" else f"/category/{encoded_value}"
        url = f"{BASE_URL}{path}"
        base_params = {"sort_by": sort_by} if sort_by else {}

        all_items: list[dict] = []
        max_id = None
        grid_total = None
        input_value = f"{browse_by}:{value}"

        while len(all_items) < max_items:
            params = dict(base_params)
            if max_id:
                params["max_id"] = max_id
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return [extract_error(input_value, "not_found")]
            if r.status_code != 200:
                return [extract_error(input_value, f"http_{r.status_code}")]

            state = extract_initial_state(r.text)
            items, more = extract_browse_page(state, browse_by, value)
            grid_total = more.get("total")
            if not items:
                break
            all_items.extend(items)
            if not more.get("is_next_max_id_present"):
                break
            max_id = more.get("next_max_id")
            if not max_id:
                break

        return wrap_browse_items(all_items[:max_items], browse_by, value, grid_total)
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(f"{browse_by}:{value}", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_listing(listing_id_or_url: str, proxy_url: str | None) -> dict:
    client = PoshmarkClient(proxy_url=proxy_url)
    try:
        url = listing_id_or_url if listing_id_or_url.startswith("http") else f"{BASE_URL}/listing/x-{listing_id_or_url}"
        r = await client.get(url)
        if r.status_code == 404:
            return extract_error(listing_id_or_url, "listing_not_found")
        if r.status_code != 200:
            return extract_error(listing_id_or_url, f"http_{r.status_code}")

        state = extract_initial_state(r.text)
        record = extract_listing(state, listing_id_or_url)
        if record is None:
            return extract_error(listing_id_or_url, "listing_not_found", "page 200'd but listingDetails was empty")
        return record
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(listing_id_or_url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_seller(username: str, proxy_url: str | None) -> dict:
    client = PoshmarkClient(proxy_url=proxy_url)
    try:
        r = await client.get(f"{BASE_URL}/closet/{username}")
        if r.status_code == 404:
            return extract_error(username, "seller_not_found")
        if r.status_code != 200:
            return extract_error(username, f"http_{r.status_code}")

        state = extract_initial_state(r.text)
        record = extract_seller(state, username)
        if record is None:
            return extract_error(username, "seller_not_found", "page 200'd but closetUserInfo was empty")
        return record
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(username, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "browse")
        valid_modes = ("browse", "listing", "seller")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        sort_by = input_data.get("sortBy")
        if sort_by and sort_by not in SORT_BY_VALUES:
            raise input_error(f"Invalid sortBy: {sort_by!r}. Must be one of {SORT_BY_VALUES}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        if mode == "browse":
            browse_by = input_data.get("browseBy", "brand")
            if browse_by not in ("brand", "category"):
                raise input_error(f"Invalid browseBy: {browse_by!r}. Must be 'brand' or 'category'.")
            value = input_data.get("value")
            if not value:
                raise input_error("Provide 'value' (a brand name or a Department-Category slug) when mode is 'browse'.")
            max_items = int(input_data.get("maxItems", 100))

            proxy_url = await proxy_config.new_url() if proxy_config else None
            records = await run_browse(browse_by, value, sort_by, max_items, proxy_url)
            Actor.log.info(f"mode=browse: {len(records)} record(s), maxItems={max_items}")
            await Actor.push_data(records)
            return

        if mode == "listing":
            ids = list(input_data.get("listingIds") or [])
            if input_data.get("listingId"):
                ids.insert(0, input_data["listingId"])
            if not ids:
                raise input_error("Provide 'listingId' or 'listingIds' when mode is 'listing'.")
            seen = set()
            ids = [i for i in ids if not (i in seen or seen.add(i))]

            async def _bounded_listing(lid: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_listing(lid, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode=listing: {len(ids)} listing(s), maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded_listing(i) for i in ids))
            return

        # mode == "seller"
        usernames = list(input_data.get("usernames") or [])
        if input_data.get("username"):
            usernames.insert(0, input_data["username"])
        if not usernames:
            raise input_error("Provide 'username' or 'usernames' when mode is 'seller'.")
        seen = set()
        usernames = [u for u in usernames if not (u in seen or seen.add(u))]

        async def _bounded_seller(u: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_seller(u, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=seller: {len(usernames)} seller(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_seller(u) for u in usernames))
