import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import IndonesiaYPClient, NotFound
from src.constants import (
    BASE_URL,
    MODES,
    PATH_CATEGORY,
    PATH_CATEGORY_CITY,
    PATH_CATEGORY_CITY_PAGE,
    PATH_CATEGORY_PAGE,
)
from src.extractor import (
    company_path_from_input,
    extract_error,
    parse_cards,
    parse_company,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


def _page_path_builder(slug: str, city: str | None):
    slug = slug.strip().strip("/").lower()
    if city:
        city = city.strip()

        def build(page: int) -> str:
            if page == 1:
                return PATH_CATEGORY_CITY.format(slug=slug, city=city)
            return PATH_CATEGORY_CITY_PAGE.format(slug=slug, city=city, page=page)
    else:

        def build(page: int) -> str:
            if page == 1:
                return PATH_CATEGORY.format(slug=slug)
            return PATH_CATEGORY_PAGE.format(slug=slug, page=page)

    return build


async def run_category(
    slug: str, city: str | None, max_items: int, proxy_url: str | None
) -> list[dict]:
    label = f"category:{slug}" + (f"/city:{city}" if city else "")
    client = IndonesiaYPClient(proxy_url=proxy_url)
    try:
        cards = await client.paginate_category(_page_path_builder(slug, city), max_items, parse_cards)
        records = []
        for c in cards:
            rec = wrap(c, label, record_type="BUSINESS_CARD")
            rec["_listingScope"] = label
            records.append(rec)
        return records
    except NotFound as e:
        return [extract_error(label, "not_found", str(e))]
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_company(raw_input: str, proxy_url: str | None) -> dict:
    path = company_path_from_input(raw_input)
    if not path:
        return extract_error(raw_input, "invalid_company_input", "expected a /company/<id>/<slug> URL or a numeric id")

    client = IndonesiaYPClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(path)
        data = parse_company(html, f"{BASE_URL}{path}")
        if not data.get("name"):
            return extract_error(raw_input, "not_a_company", f"no business name parsed from {path}")
        return wrap(data, raw_input, record_type="BUSINESS_PROFILE")
    except NotFound:
        return extract_error(raw_input, "not_found", path)
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Categories from the homepage, plus the city facets that a category
    page itself links (they differ per category, so a category slug can be
    supplied to widen the list)."""
    client = IndonesiaYPClient(proxy_url=proxy_url)
    try:
        records = []
        home = await client.get_html("/")
        cats = sorted(set(re.findall(r'href="(/category/[a-z0-9_\-]+)"', home)))
        for path in cats:
            slug = path.rsplit("/", 1)[-1]
            records.append(
                wrap({"slug": slug, "listingUrl": f"{BASE_URL}{path}"}, "reference", record_type="CATEGORY")
            )

        # City facets are only rendered on a category page; restaurants is the
        # largest category so it exposes the widest city list.
        cat_html = await client.get_html(PATH_CATEGORY.format(slug="restaurants"))
        cities = sorted(set(re.findall(r'href="/category/[a-z0-9_\-]+/city:([^"/]+)"', cat_html)))
        for city in cities:
            records.append(wrap({"city": city}, "reference", record_type="CITY"))
        return records
    except TRANSIENT as e:
        return [extract_error("reference", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "category")
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

        if mode == "category":
            slug = (input_data.get("category") or "").strip()
            if not slug:
                raise input_error("Provide 'category' when mode is 'category' (run mode=reference for the list).")
            city = (input_data.get("city") or "").strip() or None
            records = await run_category(slug, city, max_items, await new_proxy_url())
            Actor.log.info(f"mode=category {slug!r} city={city!r} -> {len(records)} record(s)")
            await Actor.push_data(records)

            if input_data.get("enrichProfiles"):
                urls = [r["profileUrl"] for r in records if r.get("profileUrl")]
                Actor.log.info(f"enrichProfiles: fetching {len(urls)} company page(s)")
                await _fetch_companies(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)
            return

        # mode == "company"
        urls = list(input_data.get("companyUrls") or [])
        if input_data.get("companyUrl"):
            urls.insert(0, input_data["companyUrl"])
        if not urls:
            raise input_error("Provide 'companyUrl' or 'companyUrls' when mode is 'company'.")
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        Actor.log.info(f"mode=company: {len(urls)} company page(s)")
        await _fetch_companies(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)


async def _fetch_companies(urls: list[str], max_concurrency: int, new_proxy_url) -> None:
    sem = asyncio.Semaphore(max_concurrency)

    async def _bounded(u: str):
        async with sem:
            record = await run_company(u, await new_proxy_url())
            await Actor.push_data(record)

    await asyncio.gather(*(_bounded(u) for u in urls))
