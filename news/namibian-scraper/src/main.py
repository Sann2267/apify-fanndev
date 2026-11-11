import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NamibianClient
from src.constants import RSS_FEED_URL, RSS_PAGE_SIZE
from src.extractor import extract_article, extract_error, extract_rss_items
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = NamibianClient(proxy_url=proxy_url)
    try:
        r = await client.get(url)
        if r.status_code == 404:
            return extract_error(url, "not_found")
        if r.status_code != 200:
            return extract_error(url, f"http_{r.status_code}")
        # UnexpectedShape propagates -- schema drift must fail the run loudly,
        # not silently disappear into a per-item error record.
        return extract_article(r.text, url)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    """WordPress RSS feed, paginated via ?paged=N (RSS_PAGE_SIZE items/page).

    Consecutive pages were observed to overlap by one item (the last item
    of page N reappears as the first item of page N+1, likely two posts
    sharing the same publish second shifting the boundary) -- dedupe by
    `guid` while paginating (see CRAWLING_METHOD.md).
    """
    client = NamibianClient(proxy_url=proxy_url)
    try:
        items: list[dict] = []
        seen_guids: set[str] = set()
        page = 1
        while len(items) < limit:
            url = RSS_FEED_URL if page == 1 else f"{RSS_FEED_URL}?paged={page}"
            r = await client.get(url)
            if r.status_code != 200:
                if page == 1:
                    raise RuntimeError(f"RSS feed {url} returned {r.status_code}")
                break  # ran out of pages -- return what we have
            page_items = extract_rss_items(r.content)
            if not page_items:
                break
            new_items = [it for it in page_items if it.get("guid") not in seen_guids]
            seen_guids.update(it.get("guid") for it in new_items)
            items.extend(new_items)
            if len(page_items) < RSS_PAGE_SIZE:
                break  # last page
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
