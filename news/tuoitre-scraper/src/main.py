import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import TuoiTreClient
from src.constants import RSS_URL
from src.extractor import extract_article, extract_error, extract_rss_items
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = TuoiTreClient(proxy_url=proxy_url)
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
    client = TuoiTreClient(proxy_url=proxy_url)
    try:
        r = await client.get(RSS_URL)
        if r.status_code != 200:
            raise RuntimeError(f"RSS feed {RSS_URL} returned {r.status_code}")
        items = extract_rss_items(r.text)
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
