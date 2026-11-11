import asyncio
from datetime import datetime, timezone

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_avis_page, fetch_contrats_json, fetch_dossiers_page
from src.constants import VALID_LIST_TYPES
from src.extractor import (
    UnexpectedShape,
    build_error_record,
    build_record,
    merge_dossier_modal_detail,
    parse_avis_page,
    parse_contrats_json,
    parse_dossiers_page,
)
from src.input_errors import input_error

TRANSIENT_EXC = (FetchFailed, RuntimeError, ConnectionError, RequestException)
# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin one
# (parallel MRO, same name) -- both listed, per the portfolio-wide Babak 22b fix.


async def run_avis(max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_avis_page(proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("avis", "blocked_or_transient", repr(e))]

    rows = parse_avis_page(html_text)  # raises UnexpectedShape -- must NOT be swallowed
    rows = rows[:max_results]
    return [build_record("avis", "S1-index-by-region", row) for row in rows]


async def run_dossiers(year: str, max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        html_text = await fetch_dossiers_page(year, proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("dossiers", "blocked_or_transient", repr(e))]

    rows = parse_dossiers_page(html_text)  # raises UnexpectedShape -- must NOT be swallowed
    rows = rows[:max_results]
    merge_dossier_modal_detail(html_text, rows)  # best-effort, never raises
    return [build_record("dossiers", "S1-dossier-archive-search", row) for row in rows]


async def run_contrats(year: str, max_results: int, proxy_url_fn) -> list[dict]:
    proxy_url = await proxy_url_fn()
    try:
        text = await fetch_contrats_json(year, proxy_url=proxy_url)
    except TRANSIENT_EXC as e:
        return [build_error_record("contrats", "blocked_or_transient", repr(e))]

    rows = parse_contrats_json(text)  # raises UnexpectedShape -- must NOT be swallowed
    rows = rows[:max_results]
    return [build_record("contrats", "S1-contrat-action-json", row) for row in rows]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        list_type = input_data.get("listType", "avis")
        if list_type not in VALID_LIST_TYPES:
            raise input_error(f"listType must be one of {VALID_LIST_TYPES}, got {list_type!r}")

        max_results = int(input_data.get("maxResults", 100))
        max_results = max(1, min(max_results, 10000))

        year = str(input_data.get("year") or datetime.now(timezone.utc).year)

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(f"listType={list_type} year={year} maxResults={max_results}")

        try:
            if list_type == "avis":
                records = await run_avis(max_results, proxy_url_fn)
            elif list_type == "dossiers":
                records = await run_dossiers(year, max_results, proxy_url_fn)
            else:  # contrats
                records = await run_contrats(year, max_results, proxy_url_fn)
        except UnexpectedShape:
            raise

        await Actor.push_data(records)
        Actor.log.info(f"Done -- pushed {len(records)} record(s) for listType={list_type}.")


if __name__ == "__main__":
    asyncio.run(main())
