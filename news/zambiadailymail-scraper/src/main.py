import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ZambiaDailyMailClient
from src.constants import (
    LATEST_CATEGORY_URL,
    WP_API_CATEGORY_BY_ID,
    WP_API_MEDIA_BY_ID,
    WP_API_POST_BY_ID,
    WP_API_TAG_BY_ID,
    WP_API_USER_BY_ID,
)
from src.extractor import (
    discover_post_id,
    extract_article_html_fallback,
    extract_article_wpapi,
    extract_error,
    extract_latest_items,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

MAX_LATEST_PAGES = 6  # 6 * 10 items/page = 60, comfortably above the 50-item input cap


async def _get_json_or_none(client: ZambiaDailyMailClient, url: str) -> dict | None:
    try:
        r = await client.get(url)
    except RuntimeError:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


async def _try_wpapi_by_id(client: ZambiaDailyMailClient, html_text: str, url: str) -> dict | None:
    """Returns a record on success, or None to fall through to S2-html."""
    post_id = discover_post_id(html_text)
    if post_id is None:
        return None  # no REST-discovery link found -- fall through

    post = await _get_json_or_none(client, WP_API_POST_BY_ID.format(post_id=post_id))
    if not isinstance(post, dict) or "id" not in post:
        return None

    author_id = post.get("author")
    media_id = post.get("featured_media")
    category_ids = post.get("categories") or []
    tag_ids = post.get("tags") or []

    author, media, categories, tags = await asyncio.gather(
        _get_json_or_none(client, WP_API_USER_BY_ID.format(user_id=author_id)) if author_id else _noop(),
        _get_json_or_none(client, WP_API_MEDIA_BY_ID.format(media_id=media_id)) if media_id else _noop(),
        asyncio.gather(*(_get_json_or_none(client, WP_API_CATEGORY_BY_ID.format(cat_id=c)) for c in category_ids)),
        asyncio.gather(*(_get_json_or_none(client, WP_API_TAG_BY_ID.format(tag_id=t)) for t in tag_ids)),
    )

    return extract_article_wpapi(post, url, author, media, categories, tags)


async def _noop():
    return None


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = ZambiaDailyMailClient(proxy_url=proxy_url)
    try:
        r = await client.get(url)
        if r.status_code == 404:
            return extract_error(url, "not_found")
        if r.status_code != 200:
            return extract_error(url, f"http_{r.status_code}")

        record = await _try_wpapi_by_id(client, r.text, url)
        if record is not None:
            return record

        # UnexpectedShape propagates -- schema drift must fail the run loudly,
        # not silently disappear into a per-item error record.
        return extract_article_html_fallback(r.text, url)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    client = ZambiaDailyMailClient(proxy_url=proxy_url)
    try:
        items: list[dict] = []
        page = 1
        while len(items) < limit and page <= MAX_LATEST_PAGES:
            page_url = LATEST_CATEGORY_URL if page == 1 else f"{LATEST_CATEGORY_URL}page/{page}/"
            r = await client.get(page_url)
            if r.status_code != 200:
                if page == 1:
                    raise RuntimeError(f"Category archive {page_url} returned {r.status_code}")
                break  # ran off the end of pagination -- stop, keep what we have
            page_items = extract_latest_items(r.text)
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
