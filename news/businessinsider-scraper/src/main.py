import asyncio
import logging
import uuid

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BiClient
from src.constants import RSS_URL
from src.extractor import extract_article, extract_error, extract_feed_items
from src.input_errors import input_error

log = logging.getLogger(__name__)

# Failed URLs are reported here instead of in the dataset -- every dataset item
# is a billable result under pay-per-event, and an error row is not a result.
ERRORS_KEY = "ERRORS"

# Feed fetches get a second shot on a fresh proxy IP before the run is failed:
# a single unlucky residential exit should not cost the user a whole run.
LATEST_ATTEMPTS = 2

# An article fetch that fails on our side (blocked exit IP, 5xx, network) gets
# retried on a fresh proxy session before it counts as failed.
ARTICLE_ATTEMPTS = 3


def _is_input_error(kind: str) -> bool:
    """True when the URL itself is the problem (bad/removed article), false
    when the fetch failed on our side (blocked, 5xx, transient network)."""
    if kind == "not_found":
        return True
    if kind.startswith("http_"):
        code = kind[5:]
        return code.isdigit() and 400 <= int(code) < 500 and int(code) not in (403, 408, 429)
    return False


def _collect_urls(input_data: dict) -> list[str]:
    urls = [str(u).strip() for u in (input_data.get("urls") or []) if str(u).strip()]
    single = str(input_data.get("url") or "").strip()
    if single:
        urls.insert(0, single)
    return urls


async def _fetch_latest_with_retry(limit: int, proxy_config) -> list[dict]:
    last_error = None
    for attempt in range(1, LATEST_ATTEMPTS + 1):
        proxy_url = await proxy_config.new_url() if proxy_config else None
        try:
            return await fetch_latest(limit, proxy_url)
        except (RuntimeError, ConnectionError, RequestException) as e:
            last_error = e
            Actor.log.warning(
                f"latest mode attempt {attempt}/{LATEST_ATTEMPTS} failed: {e!r}"
            )
    raise RuntimeError(f"Could not read the latest-headlines feed: {last_error!r}")


async def process_article(url: str, proxy_url: str | None) -> dict:
    client = BiClient(proxy_url=proxy_url)
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


async def process_article_with_retry(url: str, proxy_config) -> dict:
    """Fetch one article, moving to a fresh proxy IP when the fetch failed on our side.

    A refused warmup is a verdict on the exit address, and the client's own
    retries all go out through that same IP -- so only a new proxy session
    can clear it. A bad URL (404, other 4xx)
    is returned straight away, since another IP will not fix it.
    """
    record: dict = {}
    for attempt in range(1, ARTICLE_ATTEMPTS + 1):
        session_id = None if attempt == 1 else f"article_{uuid.uuid4().hex[:12]}"
        proxy_url = await proxy_config.new_url(session_id=session_id) if proxy_config else None
        record = await process_article(url, proxy_url)
        kind = record.get("_error")
        if not kind or _is_input_error(kind) or not proxy_config:
            return record
        if attempt < ARTICLE_ATTEMPTS:
            Actor.log.warning(
                f"{url}: attempt {attempt}/{ARTICLE_ATTEMPTS} failed ({kind}) -- "
                "retrying on a fresh proxy IP"
            )
    return record


async def fetch_latest(limit: int, proxy_url: str | None) -> list[dict]:
    client = BiClient(proxy_url=proxy_url)
    try:
        r = await client.get(RSS_URL)
        if r.status_code != 200:
            raise RuntimeError(f"RSS feed {RSS_URL} returned {r.status_code}")
        items = extract_feed_items(r.content)
        return items[:limit]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "article")

        # Input is validated before any network or proxy setup: the Actor-start
        # event is already charged by then, so a run must never die on its own
        # input after the user has paid for it.
        urls = _collect_urls(input_data) if mode == "article" else []
        if mode == "article" and not urls:
            raise input_error(
                "No article URL given. Set 'url' to a single Business Insider article URL "
                "(or 'urls' to a list of them), or switch 'mode' to 'latest' to pull the "
                "newest headlines without any URL."
            )

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "latest":
            limit = min(int(input_data.get("limit", 10)), 20)
            items = await _fetch_latest_with_retry(limit, proxy_config)
            Actor.log.info(f"latest mode: -> {len(items)} headlines")
            if not items:
                raise RuntimeError(
                    "The latest-headlines feed parsed to 0 items -- its shape has likely changed."
                )
            await Actor.push_data(items)
            await Actor.set_status_message(f"{len(items)} headline(s)")
            return

        # mode == "article"
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(url: str):
            async with sem:
                return await process_article_with_retry(url, proxy_config)

        Actor.log.info(f"article mode: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        results = await asyncio.gather(*(_bounded(u) for u in urls), return_exceptions=True)

        records: list[dict] = []
        failures: list[dict] = []
        drift: BaseException | None = None
        for url, result in zip(urls, results):
            if isinstance(result, BaseException):
                drift = drift or result
                failures.append({"url": url, "error": "unexpected_shape", "detail": repr(result)})
            elif result.get("_error"):
                failures.append(
                    {"url": url, "error": result["_error"], "detail": result.get("_errorDetail", "")}
                )
            else:
                records.append(result)

        if records:
            await Actor.push_data(records)
        if failures:
            for f in failures:
                Actor.log.warning(f"failed: {f['url']} -> {f['error']} {f['detail']}".rstrip())
            await Actor.set_value(ERRORS_KEY, failures)

        summary = f"{len(records)} article(s) extracted, {len(failures)} failed"
        Actor.log.info(summary)
        await Actor.set_status_message(
            summary + (f" -- see the '{ERRORS_KEY}' record in the key-value store" if failures else "")
        )

        if not records:
            # Nothing came back at all. An unrecognized page shape here really
            # could be schema drift on our side, so re-raise it and fail the
            # run loudly rather than hand back an empty dataset.
            if drift is not None:
                raise drift
            if any(not _is_input_error(f["error"]) for f in failures):
                raise RuntimeError(
                    f"All {len(urls)} URL(s) failed to fetch -- see the '{ERRORS_KEY}' record "
                    "in the key-value store."
                )
        # With at least one article extracted the page shape is demonstrably
        # intact, so a URL we could not parse is a bad URL (section page, dead
        # link), not drift -- it stays in ERRORS and the run still succeeds.
