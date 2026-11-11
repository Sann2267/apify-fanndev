import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import KunUzClient
from src.constants import LATEST_LIST_URL, LATEST_MAX_ITEMS
from src.extractor import UnexpectedShape, extract_article, extract_error, extract_listing_items
from src.input_errors import input_error

log = logging.getLogger(__name__)

# Observed once during cloud smoke testing (see CRAWLING_METHOD.md "Known
# limits"): a single residential exit node occasionally serves a 200 page
# that doesn't carry div.article-body/div.ql-editor, while every other
# exit node (and the same URL moments before/after) serves the real
# article cleanly. Genuinely transient/IP-specific, not schema drift --
# the same "flaky backend" class documented for dailyft-scraper/
# jamaicagleaner-scraper. UnexpectedShape gets one retry on a *fresh*
# proxy IP before it's treated as real schema drift and allowed to fail
# the run loudly.
UNEXPECTED_SHAPE_RETRIES = 2


async def _fetch_article_once(url: str, proxy_url: str | None) -> dict:
    client = KunUzClient(proxy_url=proxy_url)
    try:
        r = await client.get(url)
        if r.status_code == 404:
            return extract_error(url, "not_found")
        if r.status_code != 200:
            return extract_error(url, f"http_{r.status_code}")
        return extract_article(r.text, url)
    finally:
        await client.close()


async def process_article(url: str, proxy_config) -> dict:
    last_exc = None
    for attempt in range(UNEXPECTED_SHAPE_RETRIES):
        proxy_url = await proxy_config.new_url() if proxy_config else None
        try:
            return await _fetch_article_once(url, proxy_url)
        except UnexpectedShape as e:
            last_exc = e
            log.warning(f"UnexpectedShape on attempt {attempt + 1}/{UNEXPECTED_SHAPE_RETRIES} for {url}: {e}")
            continue
        except (RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's ConnectionError does NOT inherit from the
            # builtin ConnectionError -- both must be caught explicitly, plus
            # the broader RequestException for other curl_cffi transport
            # failures (timeouts, TLS errors, etc). See guardian-nigeria-
            # scraper/CRAWLING_METHOD.md.
            return extract_error(url, "blocked_or_transient", repr(e))
    # UnexpectedShape propagates after retries are exhausted -- schema
    # drift must fail the run loudly, not silently disappear into a
    # per-item error record.
    raise last_exc


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    client = KunUzClient(proxy_url=proxy_url)
    try:
        r = await client.get(LATEST_LIST_URL)
        if r.status_code != 200:
            raise RuntimeError(f"Listing page {LATEST_LIST_URL} returned {r.status_code}")
        items = extract_listing_items(r.text)
        return items[: min(limit, LATEST_MAX_ITEMS)]
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
            limit = min(int(input_data.get("limit", 10)), LATEST_MAX_ITEMS)
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
                record = await process_article(url, proxy_config)
                await Actor.push_data(record)

        Actor.log.info(f"article mode: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
