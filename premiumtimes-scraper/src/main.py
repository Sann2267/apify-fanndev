import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import PremiumTimesClient
from src.constants import RSS_PAGE_SIZE, RSS_URL
from src.extractor import ArticleNotFound, extract_article, extract_error, extract_rss_items
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = PremiumTimesClient(proxy_url=proxy_url)
    try:
        r = await client.get(url)
        if r.status_code == 404:
            return extract_error(url, "not_found")
        if r.status_code != 200:
            return extract_error(url, f"http_{r.status_code}")
        try:
            # UnexpectedShape propagates -- schema drift must fail the run
            # loudly, not silently disappear into a per-item error record.
            return extract_article(r.text, url)
        except ArticleNotFound:
            # Soft-404: deleted/never-existed article IDs 200-OK to the
            # homepage instead of a real 404 (see CRAWLING_METHOD.md). This
            # is an expected per-input failure, not a schema-drift crash.
            return extract_error(url, "not_found")
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    client = PremiumTimesClient(proxy_url=proxy_url)
    try:
        items: list[dict] = []
        seen_guids: set[str] = set()
        page = 1
        # /feed only returns RSS_PAGE_SIZE (15) items per page -- paginate
        # via ?paged=N until we have enough, or the feed runs dry.
        max_pages = (limit + RSS_PAGE_SIZE - 1) // RSS_PAGE_SIZE
        while len(items) < limit and page <= max_pages:
            feed_url = RSS_URL if page == 1 else f"{RSS_URL}?paged={page}"
            r = await client.get(feed_url)
            if r.status_code != 200:
                if page == 1:
                    raise RuntimeError(f"RSS feed {feed_url} returned {r.status_code}")
                break
            page_items = extract_rss_items(r.text)
            new_items = [i for i in page_items if i.get("guid") not in seen_guids]
            if not new_items:
                break
            for i in new_items:
                if i.get("guid"):
                    seen_guids.add(i["guid"])
            items.extend(new_items)
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
