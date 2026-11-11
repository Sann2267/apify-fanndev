import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import EGPUgandaClient
from src.constants import ARCHIVED_PAGE_LIMIT
from src.extractor import (
    build_record,
    clean_archived_record,
    extract_error,
    parse_bid_opening_detail,
    parse_latest_open_notices,
    parse_notice_detail,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

NOTICE_ID_FROM_URL_RE = re.compile(r"(\d+)")


async def enrich_with_detail(client: EGPUgandaClient, notice_id: str) -> dict:
    """Best-effort enrichment. Never raises -- returns whatever it manages
    to fetch, with `_detailError` set if the universal detail page itself
    failed (the opportunistic bid-opening page failing is normal/expected
    for a still-open notice and is silently skipped)."""
    extra: dict = {}
    try:
        status, html = await client.fetch_notice_detail(notice_id)
        if status == 200:
            extra.update(parse_notice_detail(html))
        else:
            extra["_detailError"] = f"HTTP {status}"
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        extra["_detailError"] = repr(e)

    try:
        status, html = await client.fetch_bid_opening_detail(notice_id)
        if status == 200 and html:
            opening = parse_bid_opening_detail(html)
            if any(opening.values()):
                extra["bid_opening_result"] = opening
    except (RuntimeError, RequestException, ConnectionError):
        pass  # opportunistic only -- a still-open notice reliably 500s here

    return extra


async def run_latest(client: EGPUgandaClient, max_results: int, fetch_details: bool, sem: asyncio.Semaphore):
    html = await client.fetch_bid_notices_page_html()
    items = parse_latest_open_notices(html)[:max_results]

    async def _one(item: dict) -> dict:
        fields = dict(item)
        if fetch_details and item.get("notice_id"):
            async with sem:
                fields.update(await enrich_with_detail(client, item["notice_id"]))
        return build_record("latest", "S1-bid-notices-live-tab", fields)

    records = await asyncio.gather(*(_one(item) for item in items))
    for record in records:
        await Actor.push_data(record)
    Actor.log.info(f"latest: pushed {len(records)} currently-open bid notice(s)")


async def run_archived(
    client: EGPUgandaClient,
    max_results: int,
    financial_year: str | None,
    fetch_details: bool,
    sem: asyncio.Semaphore,
):
    collected = 0
    start = 0
    while collected < max_results:
        length = min(ARCHIVED_PAGE_LIMIT, max_results - collected)
        try:
            body = await client.fetch_archived_bid_notices_page(start, length, financial_year)
        except (RuntimeError, RequestException, ConnectionError) as e:
            await Actor.push_data(extract_error("archived", f"start={start}", "blocked_or_transient", repr(e)))
            break
        raw_rows = body.get("data") or []
        if not raw_rows:
            break

        async def _one(raw: dict) -> dict:
            fields = clean_archived_record(raw)
            if fetch_details and fields.get("notice_id"):
                async with sem:
                    fields.update(await enrich_with_detail(client, fields["notice_id"]))
            return build_record("archived", "S1-public-bids-archived-ajax", fields)

        records = await asyncio.gather(*(_one(raw) for raw in raw_rows))
        for record in records:
            await Actor.push_data(record)
        collected += len(raw_rows)
        start += length
        if len(raw_rows) < length:
            break  # short page -- reliable end-of-results signal

    Actor.log.info(f"archived: pushed {collected} archived bid notice(s)")


async def run_detail(client: EGPUgandaClient, notice_refs: list[str], sem: asyncio.Semaphore):
    async def _one(ref: str) -> dict:
        m = NOTICE_ID_FROM_URL_RE.search(ref)
        if not m:
            return extract_error("detail", ref, "invalid_notice_id", f"Could not parse a numeric notice ID from {ref!r}")
        notice_id = m.group(1)
        async with sem:
            try:
                status, html = await client.fetch_notice_detail(notice_id)
            except (RuntimeError, RequestException, ConnectionError) as e:
                return extract_error("detail", ref, "blocked_or_transient", repr(e))
            if status != 200:
                return extract_error("detail", ref, "not_found", f"HTTP {status}")
            fields = {"notice_id": notice_id, "detail_url": f"https://egpuganda.go.ug/index/{notice_id}_egp"}
            fields.update(parse_notice_detail(html))
            try:
                op_status, op_html = await client.fetch_bid_opening_detail(notice_id)
                if op_status == 200 and op_html:
                    opening = parse_bid_opening_detail(op_html)
                    if any(opening.values()):
                        fields["bid_opening_result"] = opening
            except (RuntimeError, RequestException, ConnectionError):
                pass
            return build_record("detail", "S1-notice-detail-page", fields)

    records = await asyncio.gather(*(_one(ref) for ref in notice_refs))
    for record in records:
        await Actor.push_data(record)
    Actor.log.info(f"detail: pushed {len(records)} notice record(s)")


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode") or "latest"
        if mode not in ("latest", "archived", "detail"):
            raise input_error(f"Invalid mode {mode!r} -- expected 'latest', 'archived', or 'detail'.")

        max_results = min(int(input_data.get("maxResults", 50)), 2000)
        fetch_details = bool(input_data.get("fetchDetails", True))
        financial_year = (input_data.get("financialYear") or "").strip() or None
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        notice_ids = list(input_data.get("noticeIds") or [])

        if mode == "detail" and not notice_ids:
            raise input_error("mode='detail' requires 'noticeIds' -- one or more notice IDs or detail URLs.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        client = EGPUgandaClient(proxy_url)
        sem = asyncio.Semaphore(max_concurrency)
        try:
            Actor.log.info(f"Running mode={mode!r} maxResults={max_results} fetchDetails={fetch_details}")
            if mode == "latest":
                await run_latest(client, max_results, fetch_details, sem)
            elif mode == "archived":
                await run_archived(client, max_results, financial_year, fetch_details, sem)
            else:
                await run_detail(client, notice_ids, sem)
        finally:
            await client.close()
