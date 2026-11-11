import asyncio
import logging
import math

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import GojepClient
from src.constants import (
    AWARDED_SORT_FIELDS,
    MAX_PAGES_PER_JOB,
    OPENED_SORT_FIELDS,
    PAGE_SIZE,
)
from src.extractor import UnexpectedShape, build_error, build_record
from src.input_errors import input_error

log = logging.getLogger(__name__)

SOURCE_BY_TYPE = {
    "opened": "S1-opened-bid-details",
    "awarded": "S2-contract-award-notices",
}


async def fetch_listing(
    notice_type: str,
    max_items: int,
    sort_field: str | None,
    sort_desc: bool,
    include_bidders: bool,
    max_concurrency: int,
    proxy_config,
) -> dict:
    """Fetches up to `max_items` rows of one notice type end-to-end,
    paginating (page 1 sequentially to learn the total/pager id, remaining
    pages concurrently). Returns `{"rows": [...]}` or `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = GojepClient(proxy_url)
    fetch_page = client.fetch_opened_page if notice_type == "opened" else client.fetch_awarded_page
    try:
        first_rows, total = await fetch_page(1, sort_field, sort_desc)
        rows: list[dict] = list(first_rows)

        pages_needed = math.ceil(max_items / PAGE_SIZE)
        if total is not None:
            pages_needed = min(pages_needed, math.ceil(total / PAGE_SIZE))
        pages_needed = min(pages_needed, MAX_PAGES_PER_JOB)

        if pages_needed > 1 and len(rows) < max_items:
            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded_page(p: int):
                async with sem:
                    page_rows, _ = await fetch_page(p, sort_field, sort_desc)
                    return page_rows

            more = await asyncio.gather(*(_bounded_page(p) for p in range(2, pages_needed + 1)))
            for page_rows in more:
                rows.extend(page_rows)

        rows = rows[:max_items]

        if include_bidders and notice_type == "opened":
            sem2 = asyncio.Semaphore(max_concurrency)

            async def _attach_bidders(row: dict):
                if not row.get("resourceId"):
                    row["bidders"] = []
                    return
                async with sem2:
                    try:
                        row["bidders"] = await client.fetch_bidders(row["resourceId"])
                    except (RuntimeError, RequestException, ConnectionError) as e:
                        row["bidders"] = None
                        row["_biddersError"] = repr(e)

            await asyncio.gather(*(_attach_bidders(row) for row in rows))

        return {"rows": rows, "total": total}
    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same class name) -- both listed.
        log.warning(f"fetch_listing({notice_type!r}) failed: {e!r}")
        return {"error": build_error(notice_type, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        notice_type = input_data.get("noticeType") or "opened"
        if notice_type not in ("opened", "awarded"):
            raise input_error("'noticeType' must be 'opened' or 'awarded'")

        max_items = min(int(input_data.get("maxItems", 50)), 5000)
        sort_by = (input_data.get("sortBy") or "").strip() or None
        sort_order = input_data.get("sortOrder") or "desc"
        include_bidders = bool(input_data.get("includeBidders", False))
        max_concurrency = int(input_data.get("maxConcurrency", 3))

        sort_map = OPENED_SORT_FIELDS if notice_type == "opened" else AWARDED_SORT_FIELDS
        sort_field = sort_map.get(sort_by) if sort_by else None
        if sort_by and sort_field is None:
            raise input_error(f"'sortBy'={sort_by!r} is not valid for noticeType={notice_type!r}; valid: {sorted(sort_map)}")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        Actor.log.info(
            f"noticeType={notice_type}, maxItems={max_items}, sortBy={sort_by}, sortOrder={sort_order}, "
            f"includeBidders={include_bidders}, maxConcurrency={max_concurrency}"
        )

        outcome = await fetch_listing(
            notice_type, max_items, sort_field, sort_order == "desc", include_bidders, max_concurrency, proxy_config
        )

        if "error" in outcome:
            await Actor.push_data(outcome["error"])
            return

        rows = outcome["rows"]
        if outcome.get("total") is not None:
            Actor.log.info(f"Upstream reports {outcome['total']} total {notice_type} records; fetched {len(rows)}")
        if not rows:
            await Actor.push_data(build_error(notice_type, "not_found"))
            return

        source = SOURCE_BY_TYPE[notice_type]
        for row in rows:
            await Actor.push_data(build_record(notice_type, source, row))
