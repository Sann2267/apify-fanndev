import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_page
from src.constants import PAGE_SIZE, TENDER_LIST_URL
from src.extractor import UnexpectedShape, build_error_record, build_record, build_tender_record, parse_tender_rows

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


async def run_tenders(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()

    records: list[dict] = []
    page = 0
    while len(records) < max_results:
        try:
            html = await fetch_page(TENDER_LIST_URL, page, proxy_url=proxy_url)
        except TRANSIENT_EXC as e:
            if records:
                break  # keep what we already collected rather than discarding a partial run
            return [build_error_record("blocked_or_transient", repr(e))]

        rows = parse_tender_rows(html, "tender-list")  # raises UnexpectedShape -- must NOT be swallowed
        if not rows:
            break  # reached the last page
        records.extend(build_record(build_tender_record(r)) for r in rows)

        if len(rows) < PAGE_SIZE:
            break  # short page -- was the last one
        page += 1

    return records[:max_results]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        max_results = int(input_data.get("maxResults", 200))
        max_results = max(1, min(max_results, 10000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"maxResults={max_results}")

        records = await run_tenders(max_results, proxy_url_fn)

        await Actor.push_data(records)
        Actor.log.info(f"Done -- pushed {len(records)} record(s).")


if __name__ == "__main__":
    asyncio.run(main())
