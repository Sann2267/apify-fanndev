import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_archived_page, fetch_latest_page
from src.constants import ARCHIVED_URL, LATEST_URL, VALID_MODES
from src.extractor import UnexpectedShape, build_error_record, build_record, parse_tenders_page
from src.input_errors import input_error

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


async def run_latest(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_latest_page(proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("latest", "blocked_or_transient", repr(e))]

    rows = parse_tenders_page(html_text, LATEST_URL)  # raises UnexpectedShape -- must NOT be swallowed
    rows = rows[:max_results]
    return [build_record("latest", "S1-mdn-accordion-current", row) for row in rows]


async def run_archived(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_archived_page(proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("archived", "blocked_or_transient", repr(e))]

    rows = parse_tenders_page(html_text, ARCHIVED_URL)  # raises UnexpectedShape -- must NOT be swallowed
    rows = rows[:max_results]
    return [build_record("archived", "S1-mdn-accordion-archive", row) for row in rows]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "latest")
        if mode not in VALID_MODES:
            raise input_error(f"mode must be one of {VALID_MODES}, got {mode!r}")

        max_results = int(input_data.get("maxResults", 200))
        max_results = max(1, min(max_results, 10000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"mode={mode} maxResults={max_results}")

        if mode == "latest":
            records = await run_latest(max_results, proxy_url_fn)
        else:  # archived
            records = await run_archived(max_results, proxy_url_fn)

        await Actor.push_data(records)
        Actor.log.info(f"Done -- pushed {len(records)} record(s) for mode={mode}.")


if __name__ == "__main__":
    asyncio.run(main())
