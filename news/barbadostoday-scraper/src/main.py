import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BarbadosTodayClient
from src.constants import WP_API_POSTS_URL
from src.extractor import (
    ArticleNotFound,
    UnexpectedShape,
    extract_article_html_fallback,
    extract_article_wpapi,
    extract_error,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"/([^/]+)/?$")


def slug_from_url(url: str) -> str:
    m = SLUG_RE.search(url.split("?")[0].rstrip("/"))
    if not m:
        raise UnexpectedShape(f"Could not extract a slug from URL: {url!r}")
    return m.group(1)


async def _try_wpapi(client: BarbadosTodayClient, slug: str, url: str) -> dict | None:
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


async def _try_html_fallback(client: BarbadosTodayClient, url: str) -> dict:
    r = await client.get(url)
    if r.status_code == 404:
        return extract_error(url, "not_found")
    if r.status_code != 200:
        return extract_error(url, f"http_{r.status_code}")
    try:
        # UnexpectedShape propagates -- schema drift must fail the run
        # loudly, not silently disappear into a per-item error record.
        return extract_article_html_fallback(r.text, url)
    except ArticleNotFound:
        return extract_error(url, "not_article")


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = BarbadosTodayClient(proxy_url=proxy_url)
    try:
        slug = slug_from_url(url)
        record = await _try_wpapi(client, slug, url)
        if record is not None:
            return record
        return await _try_html_fallback(client, url)
    except (RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own `ConnectionError` (raised on a failed proxy
        # CONNECT tunnel, DNS failure, etc.) does NOT inherit from Python's
        # builtin `ConnectionError` -- its MRO is RequestException ->
        # CurlError -> OSError, a parallel hierarchy with the same class
        # name. Both are caught explicitly here so a transient proxy/network
        # hiccup degrades to a per-item error record instead of crashing the
        # whole run (see guardian-nigeria-scraper/CRAWLING_METHOD.md).
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    """S1-wpapi, no `slug` filter -- `/wp-json/wp/v2/posts` accepts
    `per_page` up to (at least) 50 in a single call, confirmed during recon,
    so no pagination loop is needed for this actor's 1-50 `limit` range.
    """
    client = BarbadosTodayClient(proxy_url=proxy_url)
    try:
        r = await client.get(WP_API_POSTS_URL, params={"per_page": str(limit), "_embed": "1"})
        if r.status_code != 200:
            raise RuntimeError(f"WP API {WP_API_POSTS_URL} returned {r.status_code}")
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError(f"WP API {WP_API_POSTS_URL} returned non-list JSON: {type(data)!r}")
        return [extract_article_wpapi(post, "latest") for post in data[:limit]]
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
