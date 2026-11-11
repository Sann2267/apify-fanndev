import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import EgpClient
from src.constants import MAX_PAGES_HARD_CAP, PAGE_SIZE
from src.extractor import (
    DETAIL_URL,
    LIST_URL,
    UnexpectedShape,
    build_detail_record,
    build_error,
    build_list_params,
    build_list_record,
    parse_detail_response,
    parse_list_response,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def _fetch_page(client: EgpClient, skip: int, top: int, fiscal_year_id: str | None):
    params = build_list_params(skip, top, fiscal_year_id)
    r = await client.get(LIST_URL, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"http_{r.status_code}: {r.text[:300]}")
    return parse_list_response(r.json())


async def run_listing(proxy_config, query: str, max_items: int, fiscal_year_id: str | None) -> list[dict]:
    """Shared implementation for both 'latest' and 'list' modes -- both
    paginate the same "Publication Plan Lots" register, sorted newest-first
    by `timestamp`. 'latest' is just this called with a small maxItems."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = EgpClient(proxy_url=proxy_url)
    try:
        records: list[dict] = []
        skip = 0
        page = 0
        while len(records) < max_items and page < MAX_PAGES_HARD_CAP:
            top = min(PAGE_SIZE, max_items - len(records))
            try:
                items, total = await _fetch_page(client, skip, top, fiscal_year_id)
            except UnexpectedShape as e:
                if records:
                    log.warning(f"page at skip={skip} unexpected shape, stopping pagination: {e}")
                    break
                return [build_error(query, "unexpected_shape", str(e))]
            if not items:
                break
            records.extend(build_list_record(query, item) for item in items)
            skip += top
            page += 1
        return records[:max_items]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail_one(lot_id: str, proxy_url: str | None) -> dict:
    """Mode 'detail' -- fetch one procurement plan lot's item-level detail
    (quantities, estimated price/currency, technical specifications,
    delivery milestones) by its lot id (the 'id' field of a 'list'/'latest'
    record)."""
    lot_id = lot_id.strip()
    if not lot_id:
        return build_error(lot_id, "invalid_input", "Empty lot id")
    client = EgpClient(proxy_url=proxy_url)
    try:
        r = await client.get(f"{DETAIL_URL}/{lot_id}")
        if r.status_code != 200:
            return build_error(lot_id, f"http_{r.status_code}", r.text[:300])
        try:
            detail = parse_detail_response(r.json())
        except UnexpectedShape as e:
            return build_error(lot_id, "unexpected_shape", str(e))
        return build_detail_record(lot_id, lot_id, detail)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return build_error(lot_id, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = (input_data.get("mode") or "latest").strip().lower()
        max_items = int(input_data.get("maxItems", 20))
        fiscal_year_id = (input_data.get("fiscalYearId") or "").strip() or None
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "latest":
            Actor.log.info(f"mode=latest max_items={max_items} fiscal_year_id={fiscal_year_id}")
            records = await run_listing(proxy_config, "latest", max_items, fiscal_year_id)
            await Actor.push_data(records)

        elif mode == "list":
            Actor.log.info(f"mode=list max_items={max_items} fiscal_year_id={fiscal_year_id}")
            records = await run_listing(proxy_config, "list", max_items, fiscal_year_id)
            await Actor.push_data(records)

        elif mode == "detail":
            ids = [str(x).strip() for x in (input_data.get("lotIds") or []) if str(x).strip()]
            if not ids:
                raise input_error("Mode 'detail' requires 'lotIds' (procurement plan lot ids).")

            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded(lot_id: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_detail_one(lot_id, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode=detail targets={len(ids)} maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded(lot_id) for lot_id in ids))

        else:
            raise input_error(f"Unknown mode {mode!r} -- expected 'latest', 'list', or 'detail'.")
