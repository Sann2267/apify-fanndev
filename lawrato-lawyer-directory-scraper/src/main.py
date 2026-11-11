import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import LawRatoClient, NotFound
from src.constants import (
    BASE_URL,
    MODES,
    PATH_ALL,
    PATH_AREA,
    PATH_CITY,
    PROFILE_PREFIX,
)
from src.extractor import (
    extract_error,
    parse_cards,
    parse_profile,
    slug_from_input,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


def _listing_path(city: str | None, area: str | None) -> tuple[str, str]:
    """City and practice area are separate upstream routes -- there is no
    combined `/lawyers/delhi/divorce` page -- so city wins when both are set
    and the caller is told about it."""
    if city:
        return PATH_CITY.format(city=city.strip().lower()), f"city:{city}"
    if area:
        return PATH_AREA.format(area=area.strip().lower().removesuffix("-lawyers")), f"area:{area}"
    return PATH_ALL, "all-india"


async def run_directory(
    city: str | None, area: str | None, max_items: int, proxy_url: str | None
) -> list[dict]:
    path, label = _listing_path(city, area)
    client = LawRatoClient(proxy_url=proxy_url)
    try:
        cards = await client.paginate_listing(path, max_items, parse_cards)
        records = []
        for c in cards:
            rec = wrap(c, label, record_type="LAWYER_CARD")
            rec["_listingScope"] = label
            records.append(rec)
        return records
    except NotFound:
        return [extract_error(label, "not_found", f"no listing at {BASE_URL}{path}")]
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_profile(raw_input: str, proxy_url: str | None) -> dict:
    slug = slug_from_input(raw_input)
    if not slug:
        return extract_error(raw_input, "empty_input")
    url = f"{BASE_URL}/{slug}"

    client = LawRatoClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(f"/{slug}")
        data = parse_profile(html, url)
        if not data.get("name"):
            return extract_error(raw_input, "not_a_profile", f"no lawyer name parsed from {url}")
        return wrap(data, raw_input, record_type="LAWYER_PROFILE")
    except NotFound:
        return extract_error(raw_input, "not_found", url)
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Read the live city and practice-area facets off the main directory
    page, so callers never have to guess a slug for `directory` mode."""
    client = LawRatoClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(PATH_ALL)
        links = set(
            re.sub(r"^https?://(?:www\.)?lawrato\.com", "", h)
            for h in re.findall(r'href=["\']([^"\'#?]+)', html)
        )
        records = []
        for city in sorted(
            l.split("/lawyers/")[1] for l in links if l.startswith("/lawyers/") and l.count("/") == 2
        ):
            records.append(
                wrap({"slug": city, "listingUrl": f"{BASE_URL}/lawyers/{city}"}, "reference", record_type="CITY")
            )
        for area in sorted(
            l.strip("/") for l in links if l.endswith("-lawyers") and l.count("/") == 1
        ):
            records.append(
                wrap(
                    {"slug": area.removesuffix("-lawyers"), "listingUrl": f"{BASE_URL}/{area}"},
                    "reference",
                    record_type="PRACTICE_AREA",
                )
            )
        return records
    except TRANSIENT as e:
        return [extract_error("reference", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "directory")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 100))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "directory":
            city = (input_data.get("city") or "").strip() or None
            area = (input_data.get("practiceArea") or "").strip() or None
            if city and area:
                Actor.log.warning(
                    "city and practiceArea are separate listings upstream -- using city and ignoring practiceArea"
                )
            records = await run_directory(city, area, max_items, await new_proxy_url())
            Actor.log.info(f"mode=directory city={city!r} area={area!r} -> {len(records)} record(s)")
            await Actor.push_data(records)

            if input_data.get("enrichProfiles"):
                urls = [r["profileUrl"] for r in records if r.get("profileUrl")]
                Actor.log.info(f"enrichProfiles: fetching {len(urls)} full profile(s)")
                await _fetch_profiles(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)
            return

        # mode == "profile"
        urls = list(input_data.get("profileUrls") or [])
        if input_data.get("profileUrl"):
            urls.insert(0, input_data["profileUrl"])
        if not urls:
            raise input_error("Provide 'profileUrl' or 'profileUrls' when mode is 'profile'.")
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        Actor.log.info(f"mode=profile: {len(urls)} profile(s)")
        await _fetch_profiles(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)


async def _fetch_profiles(urls: list[str], max_concurrency: int, new_proxy_url) -> None:
    sem = asyncio.Semaphore(max_concurrency)

    async def _bounded(u: str):
        async with sem:
            record = await run_profile(u, await new_proxy_url())
            await Actor.push_data(record)

    await asyncio.gather(*(_bounded(u) for u in urls))
