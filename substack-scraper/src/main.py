import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NotAuthorized, NotFound, SubstackClient
from src.constants import SORT_VALUES
from src.extractor import (
    build_post_record,
    build_publication_record,
    extract_error,
    host_from_pub_input,
    parse_post_url,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_post(raw_url: str, proxy_url: str | None, new_proxy_url=None) -> dict:
    parsed = parse_post_url(raw_url)
    if not parsed:
        return extract_error(raw_url, "invalid_post_url", "Expected a Substack post URL like https://<publication>/p/<slug>")
    host, slug = parsed

    client = SubstackClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
    try:
        post = await client.fetch_post(host, slug)
        return build_post_record(post, raw_url)
    except NotFound as e:
        return extract_error(raw_url, "not_found", repr(e))
    except NotAuthorized as e:
        return extract_error(raw_url, "auth_required", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(raw_url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_archive(
    raw_input: str, sort: str, max_items: int, max_concurrency: int, proxy_url: str | None, new_proxy_url=None
) -> list[dict]:
    host = host_from_pub_input(raw_input)
    client = SubstackClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
    try:
        records: list[dict] = []

        try:
            pub = await client.fetch_publication_profile(host)
            records.append(build_publication_record(pub, raw_input))
        except (NotFound, NotAuthorized, RuntimeError) as e:
            records.append(extract_error(raw_input, "publication_profile_failed", repr(e)))

        try:
            archive_items = await client.paginate_archive(host, sort, max_items)
        except NotFound as e:
            records.append(extract_error(raw_input, "not_found", repr(e)))
            return records
        except NotAuthorized as e:
            records.append(extract_error(raw_input, "auth_required", repr(e)))
            return records

        slugs = [it["slug"] for it in archive_items if it.get("slug")]
        sem = asyncio.Semaphore(max_concurrency)

        async def _fetch_one(slug: str) -> dict:
            async with sem:
                try:
                    post = await client.fetch_post(host, slug)
                    return build_post_record(post, raw_input, record_type="POST")
                except NotFound as e:
                    return extract_error(f"{raw_input}#{slug}", "not_found", repr(e))
                except NotAuthorized as e:
                    return extract_error(f"{raw_input}#{slug}", "auth_required", repr(e))
                except (RuntimeError, ConnectionError, RequestException) as e:
                    return extract_error(f"{raw_input}#{slug}", "blocked_or_transient", repr(e))

        records.extend(await asyncio.gather(*(_fetch_one(s) for s in slugs)))
        return records
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "post")
        if mode not in ("post", "archive"):
            raise input_error(f"Invalid mode: {mode!r}. Must be one of post/archive.")

        sort = input_data.get("sort", "new")
        if sort not in SORT_VALUES:
            raise input_error(f"Invalid sort: {sort!r}. Must be one of {SORT_VALUES}.")

        max_items = int(input_data.get("maxItems", 50))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        urls = list(input_data.get("urls") or [])
        if input_data.get("url"):
            urls.insert(0, input_data["url"])
        if not urls:
            raise input_error("Provide 'url' or 'urls'.")
        # de-dupe while preserving order
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(u: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                new_proxy_url = proxy_config.new_url if proxy_config else None
                if mode == "post":
                    record = await run_post(u, proxy_url, new_proxy_url)
                    await Actor.push_data(record)
                else:  # archive
                    records = await run_archive(u, sort, max_items, max_concurrency, proxy_url, new_proxy_url)
                    await Actor.push_data(records)

        Actor.log.info(f"mode={mode}: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
