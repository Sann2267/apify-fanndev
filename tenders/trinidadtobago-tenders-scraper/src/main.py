import asyncio
import logging
import math

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ProcureTTClient
from src.constants import MAX_PAGES_PER_JOB, NOTICE_TYPES
from src.extractor import UnexpectedShape, build_error, build_record
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def fetch_listing(
    notice_type: str,
    max_items: int,
    sort_field: int | None,
    sort_desc: bool,
    fetch_detail: bool,
    max_concurrency: int,
    proxy_config,
) -> dict:
    """Fetches up to `max_items` rows of one notice type end-to-end,
    paginating (page 1 sequentially to learn total/page size, remaining
    pages concurrently). Returns `{"rows": [...], "total": ...}` or
    `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ProcureTTClient(proxy_url)
    try:
        first_rows, total, page_size = await client.fetch_listing_page(notice_type, 1, sort_field, sort_desc)
        rows: list[dict] = list(first_rows)

        if page_size and total is not None and len(rows) < max_items:
            pages_needed = min(math.ceil(max_items / page_size), math.ceil(total / page_size), MAX_PAGES_PER_JOB)
            if pages_needed > 1:
                sem = asyncio.Semaphore(max_concurrency)

                async def _bounded_page(p: int):
                    async with sem:
                        page_rows, _, _ = await client.fetch_listing_page(notice_type, p, sort_field, sort_desc)
                        return page_rows

                more = await asyncio.gather(*(_bounded_page(p) for p in range(2, pages_needed + 1)))
                for page_rows in more:
                    rows.extend(page_rows)
        # else: no pagination widget on this view (e.g. pre-qualification
        # notices) -- the rows already fetched are the complete register.

        rows = rows[:max_items]

        if fetch_detail and NOTICE_TYPES[notice_type]["has_detail"]:
            sem2 = asyncio.Semaphore(max_concurrency)

            async def _attach_detail(row: dict):
                entry_id = row.get("_entryId")
                if not entry_id:
                    row["_detail"] = None
                    return
                async with sem2:
                    try:
                        row["_detail"] = await client.fetch_detail(notice_type, entry_id)
                    except (RuntimeError, RequestException, ConnectionError, UnexpectedShape) as e:
                        row["_detail"] = None
                        row["_detailError"] = repr(e)

            await asyncio.gather(*(_attach_detail(row) for row in rows))

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

        notice_type = input_data.get("noticeType") or "tenders"
        if notice_type not in NOTICE_TYPES:
            raise input_error(f"'noticeType' must be one of {sorted(NOTICE_TYPES)}")

        max_items = min(int(input_data.get("maxItems", 50)), 5000)
        sort_by = (input_data.get("sortBy") or "").strip() or None
        sort_order = input_data.get("sortOrder") or "desc"
        fetch_detail = bool(input_data.get("fetchDetail", False))
        max_concurrency = int(input_data.get("maxConcurrency", 3))

        sort_map = NOTICE_TYPES[notice_type]["sort_fields"]
        sort_field = sort_map.get(sort_by) if sort_by else None
        if sort_by and sort_field is None:
            raise input_error(f"'sortBy'={sort_by!r} is not valid for noticeType={notice_type!r}; valid: {sorted(sort_map)}")

        if fetch_detail and not NOTICE_TYPES[notice_type]["has_detail"]:
            Actor.log.warning(
                f"noticeType={notice_type!r} has no per-entry detail page upstream -- 'fetchDetail' ignored."
            )
            fetch_detail = False

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        Actor.log.info(
            f"noticeType={notice_type}, maxItems={max_items}, sortBy={sort_by}, sortOrder={sort_order}, "
            f"fetchDetail={fetch_detail}, maxConcurrency={max_concurrency}"
        )

        outcome = await fetch_listing(
            notice_type, max_items, sort_field, sort_order == "desc", fetch_detail, max_concurrency, proxy_config
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

        source = "S1-html-detail" if fetch_detail else "S1-html-table"
        for row in rows:
            await Actor.push_data(build_record(notice_type, source, row))
