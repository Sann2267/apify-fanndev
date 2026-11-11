import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import InvalidRequest, LelangClient, NotFound
from src.constants import (
    EP_CATALOG,
    EP_CATALOG_KPKNL,
    EP_CATALOG_UMKM,
    EP_CATEGORIES,
    EP_DETAIL,
    EP_FEED,
    EP_OFFICES,
    FEED_VALUES,
    MODES,
    PARAM_CATEGORY,
    PARAM_SEARCH,
)
from src.extractor import extract_error, extract_lot_id, wrap
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


def _filter_params(search: str | None, categories: list[str] | None) -> list[tuple[str, str]]:
    """`namakategori[]` is repeatable (multi-select); the `[]` suffix is
    mandatory -- sending `namakategori=X` returns HTTP 400."""
    params: list[tuple[str, str]] = []
    if search:
        params.append((PARAM_SEARCH, search))
    for c in categories or []:
        params.append((PARAM_CATEGORY, c))
    return params


async def run_catalog(
    search: str | None,
    categories: list[str] | None,
    umkm_only: bool,
    max_items: int,
    proxy_url: str | None,
) -> list[dict]:
    label = f"catalog:{search or '*'}"
    client = LelangClient(proxy_url=proxy_url)
    try:
        path = EP_CATALOG_UMKM if umkm_only else EP_CATALOG
        rows = await client.paginate(path, _filter_params(search, categories), max_items)
        return [wrap(r, label, record_type="LOT") for r in rows]
    except InvalidRequest as e:
        return [extract_error(label, "invalid_request", repr(e))]
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail(raw_input: str, proxy_url: str | None) -> dict:
    lot_id = extract_lot_id(raw_input)
    if not lot_id:
        return extract_error(raw_input, "invalid_lot_id", "no UUID found in input")

    client = LelangClient(proxy_url=proxy_url)
    try:
        data = await client.get_json(EP_DETAIL.format(lot_id=lot_id))
        payload = data.get("data")
        if not payload:
            return extract_error(raw_input, "not_found", str(data)[:300])
        return wrap(payload, raw_input, record_type="LOT_DETAIL")
    except NotFound as e:
        return extract_error(raw_input, "not_found", repr(e))
    except InvalidRequest as e:
        return extract_error(raw_input, "invalid_request", repr(e))
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def _resolve_office(client: LelangClient, wanted: str) -> dict | None:
    """Accept either a KPKNL UUID or a (case-insensitive, partial) office
    name such as "Denpasar" / "KPKNL Denpasar"."""
    offices = await client.get_list(EP_OFFICES, params=[("sortby", "nama"), ("sortdir", "asc")])
    lot_id = extract_lot_id(wanted)
    if lot_id:
        for o in offices:
            if o.get("id") == lot_id:
                return o
        return None
    needle = wanted.strip().lower()
    for o in offices:
        if needle == (o.get("nama") or "").lower():
            return o
    for o in offices:
        if needle in (o.get("nama") or "").lower():
            return o
    return None


async def run_kpknl(
    wanted: str,
    search: str | None,
    categories: list[str] | None,
    max_items: int,
    proxy_url: str | None,
) -> list[dict]:
    client = LelangClient(proxy_url=proxy_url)
    try:
        office = await _resolve_office(client, wanted)
        if not office:
            return [extract_error(wanted, "office_not_found", "no KPKNL matched; run mode=reference for the list")]
        rows = await client.paginate(
            EP_CATALOG_KPKNL.format(kpknl_id=office["id"]),
            _filter_params(search, categories),
            max_items,
        )
        records = []
        for r in rows:
            rec = wrap(r, wanted, record_type="LOT")
            rec["_kpknlName"] = office.get("nama")
            rec["_kpknlProvinsi"] = office.get("propinsi")
            rec["_kpknlKota"] = office.get("kota")
            records.append(rec)
        return records
    except InvalidRequest as e:
        return [extract_error(wanted, "invalid_request", repr(e))]
    except TRANSIENT as e:
        return [extract_error(wanted, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_feed(feed: str, max_items: int, proxy_url: str | None) -> list[dict]:
    client = LelangClient(proxy_url=proxy_url)
    try:
        rows = await client.get_list(EP_FEED[feed], params=[("limit", max_items)])
        return [wrap(r, f"feed:{feed}", record_type="LOT") for r in rows[:max_items]]
    except TRANSIENT as e:
        return [extract_error(f"feed:{feed}", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """The two lookup tables a caller needs to drive the other modes:
    the live category list (for `categories`) and all KPKNL offices with
    their province/city (for `kpknl`, which is also the only way to filter
    geographically -- `provinsi`/`kota` are silently ignored by the catalog
    endpoint)."""
    client = LelangClient(proxy_url=proxy_url)
    try:
        records = []
        for cat in await client.get_list(EP_CATEGORIES):
            records.append(wrap(cat, "reference", record_type="CATEGORY"))
        for office in await client.get_list(EP_OFFICES, params=[("sortby", "nama"), ("sortdir", "asc")]):
            records.append(wrap(office, "reference", record_type="KPKNL_OFFICE"))
        return records
    except TRANSIENT as e:
        return [extract_error("reference", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "catalog")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        search = (input_data.get("search") or "").strip() or None
        categories = list(input_data.get("categories") or [])

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "feed":
            feed = input_data.get("feed", "hot")
            if feed not in FEED_VALUES:
                raise input_error(f"Invalid feed: {feed!r}. Must be one of {FEED_VALUES}.")
            records = await run_feed(feed, max_items, await new_proxy_url())
            Actor.log.info(f"mode=feed feed={feed}: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "catalog":
            records = await run_catalog(
                search, categories, bool(input_data.get("umkmOnly")), max_items, await new_proxy_url()
            )
            Actor.log.info(
                f"mode=catalog search={search!r} categories={categories} -> {len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        if mode == "kpknl":
            offices = list(input_data.get("offices") or [])
            if input_data.get("office"):
                offices.insert(0, input_data["office"])
            if not offices:
                raise input_error("Provide 'office' or 'offices' when mode is 'kpknl'.")
            seen = set()
            offices = [o for o in offices if not (o in seen or seen.add(o))]
            Actor.log.info(f"mode=kpknl: {len(offices)} office(s)")
            for o in offices:
                records = await run_kpknl(o, search, categories, max_items, await new_proxy_url())
                Actor.log.info(f"  {o}: {len(records)} record(s)")
                await Actor.push_data(records)
            return

        # mode == "detail"
        lots = list(input_data.get("lotIds") or [])
        if input_data.get("lotId"):
            lots.insert(0, input_data["lotId"])
        if not lots:
            raise input_error("Provide 'lotId' or 'lotIds' when mode is 'detail'.")
        seen = set()
        lots = [x for x in lots if not (x in seen or seen.add(x))]

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(raw: str):
            async with sem:
                record = await run_detail(raw, await new_proxy_url())
                await Actor.push_data(record)

        Actor.log.info(f"mode=detail: {len(lots)} lot(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(x) for x in lots))
