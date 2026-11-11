import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ZppaClient
from src.constants import DETAIL_URL, HOME_URL, MAX_PAGES_HARD_CAP, OPENED_TENDERS_URL
from src.extractor import (
    UnexpectedShape,
    build_detail_record,
    build_error,
    build_latest_record,
    build_list_record,
    find_grid_id,
    parse_detail_page,
    parse_latest_widget,
    parse_opened_tenders_page,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

RESOURCE_ID_RE = re.compile(r"resourceId=(\d+)")


def _extract_resource_id(value: str) -> str | None:
    value = value.strip()
    if value.isdigit():
        return value
    m = RESOURCE_ID_RE.search(value)
    return m.group(1) if m else None


async def fetch_detail_by_id(client: ZppaClient, resource_id: str) -> tuple[dict | None, str | None]:
    """Returns (detail_dict, None) on success, or (None, error_kind).

    'login_required' is an *expected* outcome for tenders whose bid
    submission deadline has already passed (see client.py docstring) -- not
    a scraping failure, so callers surface it as a normal field/tag rather
    than crashing the run.
    """
    url = f"{DETAIL_URL}?resourceId={resource_id}"
    r = await client.get(url, allow_redirects=False)
    if r.status_code == 200:
        try:
            return parse_detail_page(r.text), None
        except UnexpectedShape as e:
            return None, f"unexpected_shape:{e}"
    if r.status_code in (301, 302, 303) and "cas/login" in (r.headers.get("location") or ""):
        return None, "login_required"
    return None, f"http_{r.status_code}"


async def run_latest(proxy_config, max_items: int) -> list[dict]:
    """Mode 'latest' -- currently-open tenders from the home page's "Latest
    Tenders" widget, enriched with the full detail page for each (detail is
    freely accessible while a tender is still open for bidding)."""
    query = "latest"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ZppaClient(proxy_url=proxy_url)
    try:
        r = await client.get(HOME_URL)
        if r.status_code != 200:
            return [build_error(query, f"http_{r.status_code}")]
        try:
            items = parse_latest_widget(r.text)
        except UnexpectedShape as e:
            return [build_error(query, "unexpected_shape", str(e))]

        items = items[:max_items]
        records = []
        for item in items:
            resource_id = item.get("resourceId")
            if not resource_id:
                records.append(build_latest_record(query, item, None, "no_resource_id"))
                continue
            detail, detail_error = await fetch_detail_by_id(client, resource_id)
            records.append(build_latest_record(query, item, detail, detail_error))
        return records
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_list(proxy_config, max_items: int) -> list[dict]:
    """Mode 'list' -- paginates the "Opened Bid Details" table
    (150k+ historical tender notices, list-level fields only: title,
    reference number, procuring entity, deadline, procurement method,
    award date, status). Walked sequentially through ONE session because
    the grid's pagination id is tied to the session's JSESSIONID cookie."""
    query = "list"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ZppaClient(proxy_url=proxy_url)
    try:
        r = await client.get(OPENED_TENDERS_URL)
        if r.status_code != 200:
            return [build_error(query, f"http_{r.status_code}")]
        try:
            rows = parse_opened_tenders_page(r.text)
        except UnexpectedShape as e:
            return [build_error(query, "unexpected_shape", str(e))]

        grid_id = find_grid_id(r.text)
        records = [build_list_record(query, row) for row in rows]

        page = 2
        while len(records) < max_items and grid_id and page <= MAX_PAGES_HARD_CAP:
            page_url = f"{OPENED_TENDERS_URL}?d-{grid_id}-p={page}"
            r = await client.get(page_url)
            if r.status_code != 200:
                log.warning(f"list page {page} returned http_{r.status_code}, stopping pagination")
                break
            try:
                rows = parse_opened_tenders_page(r.text)
            except UnexpectedShape as e:
                log.warning(f"list page {page} unexpected shape, stopping pagination: {e}")
                break
            if not rows:
                break
            records.extend(build_list_record(query, row) for row in rows)
            page += 1

        return records[:max_items]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail_one(target: str, proxy_url: str | None) -> dict:
    """Mode 'detail' -- fetch one tender by resourceId or full tender URL."""
    resource_id = _extract_resource_id(target)
    if not resource_id:
        return build_error(
            target,
            "invalid_input",
            "Could not extract a resourceId (expected a numeric id or a tender URL containing resourceId=<id>)",
        )
    client = ZppaClient(proxy_url=proxy_url)
    try:
        detail, error = await fetch_detail_by_id(client, resource_id)
        if error:
            return build_error(target, error)
        return build_detail_record(target, resource_id, detail)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return build_error(target, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = (input_data.get("mode") or "latest").strip().lower()
        max_items = int(input_data.get("maxItems", 20))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "latest":
            Actor.log.info(f"mode=latest max_items={max_items}")
            records = await run_latest(proxy_config, max_items)
            await Actor.push_data(records)

        elif mode == "list":
            Actor.log.info(f"mode=list max_items={max_items}")
            records = await run_list(proxy_config, max_items)
            await Actor.push_data(records)

        elif mode == "detail":
            ids = [str(x) for x in (input_data.get("resourceIds") or [])]
            urls = [str(x) for x in (input_data.get("tenderUrls") or [])]
            targets = [t.strip() for t in (ids + urls) if t and t.strip()]
            if not targets:
                raise input_error("Mode 'detail' requires 'resourceIds' and/or 'tenderUrls'.")

            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded(target: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_detail_one(target, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode=detail targets={len(targets)} maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded(t) for t in targets))

        else:
            raise input_error(f"Unknown mode {mode!r} -- expected 'latest', 'list', or 'detail'.")
