import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import TimesOfZambiaClient
from src.constants import RSS_FEED_URL, WP_API_POSTS_URL
from src.extractor import (
    extract_article_html_fallback,
    extract_article_wpapi,
    extract_error,
    extract_rss_items,
    slug_from_url,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

MAX_RSS_PAGES = 6  # 6 * 10 items/page = 60, comfortably above the 50-item input cap


async def _try_wpapi(client: TimesOfZambiaClient, slug: str, url: str) -> dict | None:
    """Returns a record (success or not_found), or None to fall through to S2."""
    try:
        r = await client.get(WP_API_POSTS_URL, params={"slug": slug, "_embed": "1"})
    except RuntimeError:
        return None  # exhausted retries -- try the HTML fallback before giving up
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    if not data:
        # WP API confirms no post with this slug -- authoritative not_found,
        # no need to also try the HTML fallback.
        return extract_error(url, "not_found")
    return extract_article_wpapi(data[0], url)


async def _try_html_fallback(client: TimesOfZambiaClient, url: str) -> dict:
    r = await client.get(url)
    if r.status_code == 404:
        return extract_error(url, "not_found")
    if r.status_code != 200:
        return extract_error(url, f"http_{r.status_code}")
    # UnexpectedShape propagates -- schema drift must fail the run loudly,
    # not silently disappear into a per-item error record.
    return extract_article_html_fallback(r.text, url)


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = TimesOfZambiaClient(proxy_url=proxy_url)
    try:
        slug = slug_from_url(url)
        record = await _try_wpapi(client, slug, url)
        if record is not None:
            return record
        return await _try_html_fallback(client, url)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    client = TimesOfZambiaClient(proxy_url=proxy_url)
    try:
        items: list[dict] = []
        page = 1
        while len(items) < limit and page <= MAX_RSS_PAGES:
            page_url = RSS_FEED_URL if page == 1 else f"{RSS_FEED_URL}?paged={page}"
            r = await client.get(page_url)
            if r.status_code != 200:
                if page == 1:
                    raise RuntimeError(f"RSS feed {page_url} returned {r.status_code}")
                break  # ran off the end of pagination -- stop, keep what we have
            page_items = extract_rss_items(r.content)
            if not page_items:
                break
            items.extend(page_items)
            page += 1
        return items[:limit]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "article")
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "latest":
            limit = min(int(input_data.get("limit", 10)), 50)
            proxy_url = await proxy_config.new_url() if proxy_config else None
            items = await fetch_latest(limit, proxy_url)
            Actor.log.info(f"latest mode: -> {len(items)} headlines")
            await Actor.push_data(items)
            return

        # mode == "article"
        urls = list(input_data.get("urls") or [])
        if input_data.get("url"):
            urls.insert(0, input_data["url"])
        if not urls:
            raise input_error("Provide 'url' or 'urls' when mode is 'article'.")

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(url: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await process_article(url, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"article mode: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
