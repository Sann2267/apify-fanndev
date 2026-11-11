"""Mode dispatch for the Medium engagement Actor.

Which strategy a mode uses is decided by what each surface actually yields:

* ``tag``         -- Apollo cache. 35 posts with claps, responses and paywall flag.
* ``author``      -- Apollo cache. 10 posts, same fields.
* ``publication`` -- **RSS**, because a publication's HTML page seeds 167
  hollow post references and carries no usable article. RSS gives 10 complete
  ones with the body HTML, and no engagement figures -- ``_source`` says which
  you got.
* ``post``        -- Apollo cache: one article with its paragraphs.
* ``reference``   -- probes every surface and reports the measured yields,
  including the hollow-record count on a publication page.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, MediumClient, NotFound
from src.constants import (
    EXPECTED_POSTS,
    MIN_FEED_BYTES,
    MODES,
    SECTION_PATHS,
    TAG_SECTIONS,
    URL_AUTHOR,
    URL_FEED_PUBLICATION,
    URL_POST,
    URL_TAG,
    URL_TAG_SECTION,
)
from src.extractor import (
    NoApolloState,
    extract_apollo,
    extract_error,
    parse_apollo_posts,
    parse_feed,
    parse_post_detail,
    wrap_reference,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (Blocked, RuntimeError, ConnectionError)

RECORD_TYPES = {"reference": "SURFACE", "error": "ERROR"}


def envelope(record: dict, input_value: str, record_type: str | None = None) -> dict:
    """The portfolio's mandatory meta fields (.ai/conventions/dataset-envelope.md)."""
    record.setdefault("_input", input_value)
    record.setdefault("_source", "none")
    record["_scrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_source = RECORD_TYPES.get(record["_source"])
    record.setdefault("recordType", by_source or record_type or "POST")
    return record


def normalize_tag(raw: str) -> str:
    """'Artificial Intelligence', a /tag/ URL or a slug all become the slug."""
    value = (raw or "").strip()
    m = re.search(r"/tag/([^/?#]+)", value)
    if m:
        return m.group(1)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_handle(raw: str) -> str:
    value = (raw or "").strip()
    m = re.search(r"/@([^/?#]+)", value)
    if m:
        return m.group(1)
    return value.lstrip("@")


def normalize_publication(raw: str) -> str:
    value = (raw or "").strip()
    m = re.search(r"medium\.com/(?:feed/)?([^/@?#]+)", value)
    if m:
        return m.group(1)
    return value.strip("/")


def normalize_post_path(raw: str) -> str:
    """A Medium article URL becomes the path Medium serves it under."""
    value = (raw or "").strip()
    m = re.search(r"medium\.com/(.+)$", value)
    if m:
        return m.group(1).split("?")[0].strip("/")
    return value.split("?")[0].strip("/")


async def _fetch_posts(
    client: MediumClient, url: str, source_label: str, input_value: str, expected: int
) -> tuple[list[dict], dict]:
    html, profile = await client.get(url)
    records, hollow = parse_apollo_posts(html, source_label, input_value)
    stats = {"hollowSkipped": hollow, "tlsProfile": profile, "expected": expected}
    if hollow and not records:
        # The publication-page trap: references without data.
        raise NoApolloState(
            f"{url} carried {hollow} post reference(s) but not one of them holds an "
            f"article -- Medium seeds the cache with ids it loads client-side. Use "
            f"mode 'publication', which reads the feed instead."
        )
    if records and len(records) < expected * 0.4:
        log.warning(
            f"{url} yielded {len(records)} post(s), well below the {expected} measured "
            f"during recon -- the page shape may have changed"
        )
    return records, stats


async def run_tags(
    tags: list[str], section: str, max_items: int, max_concurrency: int, proxy_url_factory, push
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        slug = normalize_tag(raw)
        if not slug:
            await push([extract_error(raw, "invalid_tag", "expected a tag name, slug or /tag/ URL")], raw)
            return
        url = (
            URL_TAG.format(slug=slug)
            if section == "top"
            else URL_TAG_SECTION.format(slug=slug, section=SECTION_PATHS[section])
        )
        async with sem:
            client = MediumClient(proxy_url=await proxy_url_factory())
            try:
                records, stats = await _fetch_posts(
                    client, url, f"medium-tag-apollo-{section}", raw, EXPECTED_POSTS[section]
                )
                for record in records:
                    record["tagQueried"] = slug
                    record["tagSection"] = section
            except NotFound:
                records = [extract_error(slug, "not_found", f"no Medium tag {slug!r}")]
            except NoApolloState as exc:
                records = [extract_error(slug, "shape_changed", str(exc))]
            except TRANSIENT as exc:
                records = [extract_error(slug, "blocked_or_transient", repr(exc))]

            async with lock:
                records = records[: max(0, max_items - pushed)]
                pushed += len(records)
            await push(records, raw)

    await asyncio.gather(*(one(t) for t in tags))
    return pushed


async def run_authors(
    handles: list[str], max_items: int, max_concurrency: int, proxy_url_factory, push
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        handle = normalize_handle(raw)
        if not handle:
            await push([extract_error(raw, "invalid_author", "expected @handle or a profile URL")], raw)
            return
        url = URL_AUTHOR.format(handle=handle)
        async with sem:
            client = MediumClient(proxy_url=await proxy_url_factory())
            try:
                records, _ = await _fetch_posts(
                    client, url, "medium-author-apollo", raw, EXPECTED_POSTS["author"]
                )
                for record in records:
                    record["authorQueried"] = handle
            except NotFound:
                records = [extract_error(handle, "not_found", f"no Medium author @{handle}")]
            except NoApolloState as exc:
                records = [extract_error(handle, "shape_changed", str(exc))]
            except TRANSIENT as exc:
                records = [extract_error(handle, "blocked_or_transient", repr(exc))]

            async with lock:
                records = records[: max(0, max_items - pushed)]
                pushed += len(records)
            await push(records, raw)

    await asyncio.gather(*(one(h) for h in handles))
    return pushed


async def run_publications(
    slugs: list[str], max_items: int, max_concurrency: int, proxy_url_factory, push
) -> int:
    """Publications come from the feed. See the module docstring for why."""
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        slug = normalize_publication(raw)
        if not slug:
            await push(
                [extract_error(raw, "invalid_publication", "expected a publication slug or URL")], raw
            )
            return
        url = URL_FEED_PUBLICATION.format(slug=slug)
        async with sem:
            client = MediumClient(proxy_url=await proxy_url_factory())
            try:
                xml, _ = await client.get(url, min_bytes=MIN_FEED_BYTES)
                records = parse_feed(xml, "medium-publication-rss", raw)
                if not records:
                    records = [
                        extract_error(
                            slug,
                            "no_items_in_feed",
                            f"the feed for {slug!r} parsed but carried no item -- check the "
                            f"slug, or the publication has published nothing",
                        )
                    ]
                else:
                    for record in records:
                        record["publicationSlug"] = slug
            except NotFound:
                records = [extract_error(slug, "not_found", f"no feed for publication {slug!r}")]
            except TRANSIENT as exc:
                records = [extract_error(slug, "blocked_or_transient", repr(exc))]

            async with lock:
                records = records[: max(0, max_items - pushed)]
                pushed += len(records)
            await push(records, raw)

    await asyncio.gather(*(one(s) for s in slugs))
    return pushed


async def run_posts(
    urls: list[str], max_items: int, max_concurrency: int, proxy_url_factory, push
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        path = normalize_post_path(raw)
        if not path:
            await push([extract_error(raw, "invalid_post", "expected a Medium article URL")], raw)
            return
        async with sem:
            client = MediumClient(proxy_url=await proxy_url_factory())
            try:
                html, _ = await client.get(URL_POST.format(path=path))
                records = [parse_post_detail(html, raw)]
            except NotFound:
                records = [extract_error(path, "not_found", "no article at this URL")]
            except NoApolloState as exc:
                records = [extract_error(path, "shape_changed", str(exc))]
            except TRANSIENT as exc:
                records = [extract_error(path, "blocked_or_transient", repr(exc))]

            async with lock:
                records = records[: max(0, max_items - pushed)]
                pushed += len(records)
            await push(records, raw)

    await asyncio.gather(*(one(u) for u in urls))
    return pushed


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe every surface and report the yields this Actor's design rests on."""
    client = MediumClient(proxy_url=proxy_url)
    url = URL_TAG.format(slug="artificial-intelligence")
    try:
        html, profile = await client.get(url)
        posts, hollow = parse_apollo_posts(html, "medium-tag-apollo-top", "reference")
        sample = {
            "tagPostsUsable": len(posts),
            "tagPostsHollow": hollow,
            "expectedForTagTop": EXPECTED_POSTS["top"],
            "samplePost": posts[0]["title"] if posts else None,
            "sampleClaps": posts[0]["clapCount"] if posts else None,
            "samplePaywalled": posts[0]["isPaywalled"] if posts else None,
        }

        # Re-test the publication trap: is the HTML page still hollow?
        try:
            pub_html, _ = await client.get("https://medium.com/better-programming")
            pub_cache = extract_apollo(pub_html)
            pub_refs = [k for k in pub_cache if k.startswith("Post:")]
            usable = [
                k for k in pub_refs if isinstance(pub_cache[k], dict) and pub_cache[k].get("title")
            ]
            sample["publicationPagePostRefs"] = len(pub_refs)
            sample["publicationPageUsablePosts"] = len(usable)
            sample["publicationStrategy"] = "rss" if not usable else "apollo-now-usable"
        except Exception as exc:  # noqa: BLE001 -- this is a probe within a probe
            sample["publicationProbeError"] = repr(exc)[:160]

        # And confirm the feed still works for publications.
        try:
            feed_xml, _ = await client.get(
                URL_FEED_PUBLICATION.format(slug="better-programming"), min_bytes=MIN_FEED_BYTES
            )
            feed_items = parse_feed(feed_xml, "medium-publication-rss", "reference")
            sample["publicationFeedItems"] = len(feed_items)
            sample["publicationFeedCarriesBody"] = bool(
                feed_items and feed_items[0].get("contentHtml")
            )
        except Exception as exc:  # noqa: BLE001
            sample["feedProbeError"] = repr(exc)[:160]

        note = "payload parsed" if posts else "200 but no usable post in the cache"
        if sample.get("publicationStrategy") == "apollo-now-usable":
            note += (
                " -- NOTE: publication pages now carry usable posts, which they did not on "
                "2026-09-18. Publication mode could switch from RSS to Apollo and gain "
                "engagement figures."
            )
        return [wrap_reference(url, bool(posts), note, sample, profile)]
    except Exception as exc:  # noqa: BLE001 -- a probe reports, it never raises
        return [wrap_reference(url, False, repr(exc))]


def _clean_list(input_data: dict, single_key: str, list_key: str) -> list[str]:
    values = list(input_data.get(list_key) or [])
    if input_data.get(single_key):
        values.insert(0, input_data[single_key])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "tag")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        section = input_data.get("tagSection", "top")
        if section not in TAG_SECTIONS:
            raise input_error(f"Invalid tagSection: {section!r}. Must be one of {TAG_SECTIONS}.")

        max_items = int(input_data.get("maxItems", 200))
        max_concurrency = int(input_data.get("maxConcurrency", 3))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict], input_value: str):
            if records:
                await Actor.push_data([envelope(r, input_value) for r in records])

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(
                f"mode=reference: available={records[0].get('isAvailable')} "
                f"tls={records[0].get('winningTlsProfile')} {records[0].get('sample')}"
            )
            await push(records, "reference")
            return

        if mode == "tag":
            tags = _clean_list(input_data, "tag", "tags")
            if not tags:
                raise input_error("Provide 'tag' or 'tags' for mode 'tag', e.g. 'artificial-intelligence'.")
            count = await run_tags(tags, section, max_items, max_concurrency, new_proxy_url, push)
            Actor.log.info(f"mode=tag section={section} tags={len(tags)} -> {count} record(s)")
            return

        if mode == "author":
            handles = _clean_list(input_data, "author", "authors")
            if not handles:
                raise input_error("Provide 'author' or 'authors' for mode 'author', e.g. '@medium'.")
            count = await run_authors(handles, max_items, max_concurrency, new_proxy_url, push)
            Actor.log.info(f"mode=author authors={len(handles)} -> {count} record(s)")
            return

        if mode == "publication":
            slugs = _clean_list(input_data, "publication", "publications")
            if not slugs:
                raise input_error(
                    "Provide 'publication' or 'publications' for mode 'publication', "
                    "e.g. 'better-programming'."
                )
            count = await run_publications(slugs, max_items, max_concurrency, new_proxy_url, push)
            Actor.log.info(f"mode=publication pubs={len(slugs)} -> {count} record(s)")
            return

        urls = _clean_list(input_data, "postUrl", "postUrls")
        if not urls:
            raise input_error("Provide 'postUrl' or 'postUrls' for mode 'post'.")
        count = await run_posts(urls, max_items, max_concurrency, new_proxy_url, push)
        Actor.log.info(f"mode=post posts={len(urls)} -> {count} record(s)")
