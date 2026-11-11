import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import (
    FetchFailed,
    fetch_notices_page,
    fetch_tenders_page,
    resolve_category_id,
    resolve_notices_category_id,
)
from src.constants import PER_PAGE, VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_error_record,
    build_notice_record,
    build_record,
    build_tender_record,
    parse_wp_json_list,
)
from src.input_errors import input_error

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


async def run_tenders(max_results: int, category_slug: str | None, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    category_id = None
    if category_slug:
        try:
            category_id = await resolve_category_id(category_slug, proxy_url=proxy_url)
        except TRANSIENT_EXC as e:
            return [build_error_record("tenders", "blocked_or_transient", repr(e))]
        if category_id is None:
            return [build_error_record("tenders", "category_not_found", f"No category with slug={category_slug!r}")]

    records: list[dict] = []
    page = 1
    while len(records) < max_results:
        try:
            body, headers = await fetch_tenders_page(page, category_id, proxy_url=proxy_url)
        except TRANSIENT_EXC as e:
            if records:
                break  # keep what we already collected rather than discarding a partial run
            return [build_error_record("tenders", "blocked_or_transient", repr(e))]

        rows = parse_wp_json_list(body, "aanbestedingen CPT")  # raises UnexpectedShape -- must NOT be swallowed
        if not rows:
            break
        records.extend(build_record("tenders", build_tender_record(r)) for r in rows)

        total_pages = int(headers.get("x-wp-totalpages", page))
        if page >= total_pages or len(rows) < PER_PAGE:
            break
        page += 1

    return records[:max_results]


async def run_notices(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        category_id = await resolve_notices_category_id(proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("notices", "blocked_or_transient", repr(e))]

    records: list[dict] = []
    page = 1
    while len(records) < max_results:
        try:
            body, headers = await fetch_notices_page(page, category_id, proxy_url=proxy_url)
        except TRANSIENT_EXC as e:
            if records:
                break
            return [build_error_record("notices", "blocked_or_transient", repr(e))]

        rows = parse_wp_json_list(body, "posts?categories=Aanbestedingen")  # raises UnexpectedShape
        if not rows:
            break
        records.extend(build_record("notices", build_notice_record(r)) for r in rows)

        total_pages = int(headers.get("x-wp-totalpages", page))
        if page >= total_pages or len(rows) < PER_PAGE:
            break
        page += 1

    return records[:max_results]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        list_type = input_data.get("listType", "tenders")
        if list_type not in VALID_LIST_TYPES:
            raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")

        max_results = int(input_data.get("maxResults", 100))
        max_results = max(1, min(max_results, 10000))

        category_slug = (input_data.get("categorySlug") or "").strip() or None

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"listType={list_type} categorySlug={category_slug} maxResults={max_results}")

        try:
            if list_type == "tenders":
                records = await run_tenders(max_results, category_slug, proxy_url_fn)
            else:  # notices
                records = await run_notices(max_results, proxy_url_fn)
        except UnexpectedShape:
            raise

        await Actor.push_data(records)
        Actor.log.info(f"Done -- pushed {len(records)} record(s) for listType={list_type}.")


if __name__ == "__main__":
    asyncio.run(main())
