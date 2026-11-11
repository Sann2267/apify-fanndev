import asyncio
import logging
from datetime import datetime, timezone

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ThePeninsulaClient
from src.constants import SITEMAP_INDEX_URL, article_sitemap_url
from src.extractor import extract_article, extract_error, extract_sitemap_items
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = ThePeninsulaClient(proxy_url=proxy_url)
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


async def _fetch_month_shard(client: ThePeninsulaClient, year: int, month: int) -> list[dict]:
    url = article_sitemap_url(year, month)
    r = await client.get(url)
    if r.status_code != 200:
        return []
    return extract_sitemap_items(r.text)


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    """No RSS feed exists on this site (see CRAWLING_METHOD.md) -- 'latest'
    mode reads the current month's Google News sitemap shard, newest-first.
    Falls back to the previous month's shard if the current one doesn't
    have enough items yet (e.g. run on the 1st-2nd of a new month).
    """
    client = ThePeninsulaClient(proxy_url=proxy_url)
    try:
        # First confirm the sitemap index itself is alive (fail loud if not --
        # this is a genuine schema-drift signal, not a per-item failure).
        r = await client.get(SITEMAP_INDEX_URL)
        if r.status_code != 200:
            raise RuntimeError(f"Sitemap index {SITEMAP_INDEX_URL} returned {r.status_code}")

        now = datetime.now(timezone.utc)
        items = await _fetch_month_shard(client, now.year, now.month)

        if len(items) < limit:
            prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
            items += await _fetch_month_shard(client, prev_year, prev_month)

        if not items:
            raise RuntimeError("Both current and previous month sitemap shards returned no items.")

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
