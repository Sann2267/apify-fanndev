import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_page
from src.constants import AWARDS_URL, CURRENT_TENDERS_URL, VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_award_record,
    build_current_record,
    build_error_record,
    build_record,
    parse_award_rows,
    parse_current_cards,
)
from src.input_errors import input_error

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


async def run_current(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html = await fetch_page(CURRENT_TENDERS_URL, proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("current", "blocked_or_transient", repr(e))]

    rows = parse_current_cards(html, "current")  # raises UnexpectedShape -- must NOT be swallowed
    records = [build_record("current", build_current_record(r)) for r in rows]
    return records[:max_results]


async def run_awards(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html = await fetch_page(AWARDS_URL, proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("awards", "blocked_or_transient", repr(e))]

    rows = parse_award_rows(html, "awards")  # raises UnexpectedShape
    records = [build_record("awards", build_award_record(r)) for r in rows]
    return records[:max_results]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        list_type = input_data.get("listType", "current")
        if list_type not in VALID_LIST_TYPES:
            raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")

        max_results = int(input_data.get("maxResults", 500))
        max_results = max(1, min(max_results, 10000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"listType={list_type} maxResults={max_results}")

        if list_type == "current":
            records = await run_current(max_results, proxy_url_fn)
        else:  # awards
            records = await run_awards(max_results, proxy_url_fn)

        await Actor.push_data(records)
        Actor.log.info(f"Done -- pushed {len(records)} record(s) for listType={list_type}.")


if __name__ == "__main__":
    asyncio.run(main())
