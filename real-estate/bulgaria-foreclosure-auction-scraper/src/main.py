"""Mode dispatch for the Bulgarian foreclosure auction Actor."""

import asyncio
import logging
import re

from apify import Actor

from src.client import BCPEAClient, BlockedUpstream, PropertyNotFound
from src.constants import (
    MAX_PERPAGE,
    MAX_RANGE,
    MODES,
    URL_LIST,
    URL_PROPERTY,
)
from src.extractor import (
    extract_error,
    parse_list,
    parse_property,
    total_pages,
    wrap_reference,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, RuntimeError, ConnectionError)


def normalize_id(raw: str) -> str:
    """Accepts '92433' or any sales.bcpea.org/properties/92433 URL."""
    value = (raw or "").strip()
    m = re.search(r"/properties/(\d+)", value)
    if m:
        return m.group(1)
    return value if value.isdigit() else ""


async def run_list(
    max_items: int,
    perpage: int,
    start_page: int,
    fetch_details: bool,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    """Page the active-sales list.

    Cards already carry court, agent, bidding period and announcement date, so
    the list alone is a usable dataset; ``fetch_details`` adds the description,
    area and agent contact block at the cost of one request per sale.
    """
    client = BCPEAClient(proxy_url=await proxy_url_factory())
    pushed = 0
    try:
        page = start_page
        pages_known = None
        while pushed < max_items:
            html = await client.get_html(URL_LIST.format(perpage=perpage, page=page))
            if pages_known is None:
                pages_known = total_pages(html)
                log.info(f"list: {pages_known} page(s) at perpage={perpage}")
            records = parse_list(html, page)
            if not records:
                break

            if fetch_details:
                records = await _enrich(records, max_concurrency, proxy_url_factory)

            records = records[: max_items - pushed]
            for record in records:
                record["totalPages"] = pages_known
            await push(records)
            pushed += len(records)

            page += 1
            if pages_known and page > pages_known:
                break
        return pushed
    finally:
        await client.close()


async def _enrich(records: list[dict], max_concurrency: int, proxy_url_factory) -> list[dict]:
    """Replace each list row with its full detail row, keeping the list row if
    the detail page fails -- a partial record beats a dropped one."""
    sem = asyncio.Semaphore(max_concurrency)

    async def one(record: dict) -> dict:
        async with sem:
            client = BCPEAClient(proxy_url=await proxy_url_factory())
            try:
                html = await client.get_html(URL_PROPERTY.format(property_id=record["propertyId"]))
                detailed = parse_property(record["propertyId"], html)
                detailed["listPage"] = record.get("listPage")
                detailed["_input"] = record["_input"]
                return detailed
            except (PropertyNotFound, ValueError, *TRANSIENT) as e:
                record["_detailError"] = repr(e)
                return record
            finally:
                await client.close()

    return list(await asyncio.gather(*(one(r) for r in records)))


async def run_properties(
    identifiers: list[str], max_items: int, max_concurrency: int, proxy_url_factory, push
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        property_id = normalize_id(raw)
        if not property_id:
            await push([extract_error(raw, "invalid_id", "expected a numeric property id or a portal URL")])
            return
        async with sem:
            client = BCPEAClient(proxy_url=await proxy_url_factory())
            try:
                html = await client.get_html(URL_PROPERTY.format(property_id=property_id))
                records = [parse_property(property_id, html)]
            except PropertyNotFound:
                records = [extract_error(property_id, "not_found", "no sale published under this id")]
            except ValueError as e:
                records = [extract_error(property_id, "shape_changed", str(e))]
            except TRANSIENT as e:
                records = [extract_error(property_id, "blocked_or_transient", repr(e))]
            finally:
                await client.close()

            async with lock:
                if pushed >= max_items:
                    return
                pushed += len(records)
            await push(records)

    await asyncio.gather(*(one(i) for i in identifiers))
    return pushed


async def run_reference(proxy_url: str | None) -> list[dict]:
    client = BCPEAClient(proxy_url=proxy_url)
    url = URL_LIST.format(perpage=12, page=1)
    try:
        html = await client.get_html(url)
        records = parse_list(html, 1)
        pages = total_pages(html)
        sample = {
            "cardsOnPage": len(records),
            "totalPages": pages,
            "estimatedActiveSales": (pages or 0) * 12 if pages else None,
            "newestPropertyId": records[0]["propertyId"] if records else None,
            "sampleCourt": records[0]["districtCourt"] if records else None,
            "sampleBiddingEnd": records[0]["biddingEnd"] if records else None,
        }
        return [wrap_reference(url, bool(records), "payload parsed" if records else "no cards parsed", sample)]
    except Exception as e:  # noqa: BLE001 -- a probe reports, never raises
        return [wrap_reference(url, False, repr(e))]
    finally:
        await client.close()


def _clean_ids(input_data: dict) -> list[str]:
    values = list(input_data.get("propertyIds") or [])
    if input_data.get("propertyId"):
        values.insert(0, input_data["propertyId"])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "list")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        perpage = min(max(1, int(input_data.get("perPage", 48))), MAX_PERPAGE)

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict]):
            if records:
                await Actor.push_data(records)

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: available={records[0].get('isAvailable')} {records[0].get('sample')}")
            await push(records)
            return

        if mode == "list":
            count = await run_list(
                max_items,
                perpage,
                max(1, int(input_data.get("startPage", 1))),
                bool(input_data.get("fetchDetails", False)),
                max_concurrency,
                new_proxy_url,
                push,
            )
            Actor.log.info(f"mode=list perpage={perpage} -> {count} record(s)")
            return

        if mode == "range":
            start = normalize_id(str(input_data.get("startId") or ""))
            if not start:
                raise input_error("Provide 'startId' (a numeric property id) for mode 'range'.")
            count = int(input_data.get("rangeCount", 50))
            if count < 1 or count > MAX_RANGE:
                raise input_error(f"'rangeCount' must be between 1 and {MAX_RANGE}.")
            ids = [str(int(start) + i) for i in range(count)]
            Actor.log.info(f"mode=range: {ids[0]}..{ids[-1]}")
            pushed = await run_properties(ids, max_items, max_concurrency, new_proxy_url, push)
            Actor.log.info(f"mode=range -> {pushed} record(s)")
            return

        identifiers = _clean_ids(input_data)
        if not identifiers:
            raise input_error("Provide 'propertyId' or 'propertyIds' for mode 'property'.")
        pushed = await run_properties(identifiers, max_items, max_concurrency, new_proxy_url, push)
        Actor.log.info(f"mode=property ids={len(identifiers)} -> {pushed} record(s)")
