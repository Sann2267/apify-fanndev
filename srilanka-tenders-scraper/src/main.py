from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, NotFound, fetch_archive_page, fetch_current_notices_page
from src.constants import MAX_ARCHIVE_PAGES_PER_RUN
from src.extractor import (
    UnexpectedShape,
    build_archive_record,
    build_current_record,
    build_error_record,
    parse_archive_page,
    parse_current_notices,
)
from src.input_errors import input_error


async def run_latest(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_current_notices_page(proxy_url=proxy_url)
    except (FetchFailed, NotFound, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError/RequestException does not
        # inherit from Python's builtin ConnectionError -- both listed, per
        # this portfolio's Babak 22b fix.
        return [build_error_record("latest", "blocked_or_transient", repr(e))]

    parsed = parse_current_notices(html_text)  # raises UnexpectedShape -- must NOT be swallowed, per project convention
    notices = parsed["notices"][:max_results]
    if not notices:
        Actor.log.info("mode=latest: matched 0 current notices.")
    return [build_current_record(n, parsed["count"]) for n in notices]


async def run_archive(start_page: int, max_results: int, proxy_url_fn) -> list[dict]:
    records: list[dict] = []
    page = start_page
    pages_fetched = 0
    total_count = None

    while len(records) < max_results and pages_fetched < MAX_ARCHIVE_PAGES_PER_RUN:
        proxy_url = await proxy_url_fn()
        try:
            html_text = await fetch_archive_page(page, proxy_url=proxy_url)
        except NotFound:
            # A 404 here means we've walked past the last real archive page
            # -- a legitimate, expected end-of-data signal, not an error.
            Actor.log.info(f"mode=archive: page {page} does not exist -- reached end of archive.")
            break
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            records.append(build_error_record(f"archive:page{page}", "blocked_or_transient", repr(e)))
            break

        parsed = parse_archive_page(html_text)  # raises UnexpectedShape -- must NOT be swallowed
        total_count = parsed["count"]
        pages_fetched += 1

        if not parsed["sections"]:
            Actor.log.info(f"mode=archive: page {page} returned 0 sections -- treating as end of archive.")
            break

        for section in parsed["sections"]:
            records.append(build_archive_record(section, page, total_count))
            if len(records) >= max_results:
                break

        page += 1

    if total_count is not None and records and "_error" not in records[-1]:
        Actor.log.info(f"mode=archive: fetched {len(records)} record(s) across {pages_fetched} page(s) (site reports {total_count} total historical notices).")
    return records


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "latest")
        if mode not in ("latest", "archive"):
            raise input_error(f"mode must be 'latest' or 'archive', got {mode!r}")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        max_results = int(input_data.get("maxResults", 50))
        max_results = max(1, min(max_results, 5000))

        if mode == "latest":
            Actor.log.info(f"mode=latest maxResults={max_results}")
            try:
                records = await run_latest(max_results, proxy_url_fn)
            except UnexpectedShape:
                raise
            await Actor.push_data(records)
            return

        # mode == "archive"
        start_page = int(input_data.get("archiveStartPage", 1))
        start_page = max(1, start_page)

        Actor.log.info(f"mode=archive startPage={start_page} maxResults={max_results}")
        try:
            records = await run_archive(start_page, max_results, proxy_url_fn)
        except UnexpectedShape:
            raise
        await Actor.push_data(records)
