import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import UmucyoClient
from src.extractor import build_record, extract_error, parse_detail, parse_list_page
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def enrich_with_detail(client: UmucyoClient, detail_ref: str) -> dict:
    """Best-effort enrichment. Never raises -- returns whatever it manages
    to fetch, with `_detailError` set on failure."""
    try:
        tend_refer_no, tend_stage_cd, tend_type_cd = detail_ref.split("|", 2)
    except ValueError:
        return {"_detailError": f"malformed detail_ref {detail_ref!r}"}
    try:
        html = await client.fetch_detail(tend_refer_no, tend_stage_cd, tend_type_cd)
        return parse_detail(html)
    except (RuntimeError, RequestException, ConnectionError, OSError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"_detailError": repr(e)}


def _build_filters(input_data: dict) -> dict:
    filters = {}
    mapping = {
        "tenderType": "tendTypeCd",
        "tenderMethod": "tendMthodCd",
        "tenderStatus": "tendStatCd",
        "procuringEntityName": "peCdNm",
        "tenderNo": "tendReferNo",
        "tenderName": "tendNm",
        "invitationDateFrom": "pubcatFromDt",
        "invitationDateTo": "pubcatToDt",
    }
    for input_key, form_key in mapping.items():
        value = (input_data.get(input_key) or "").strip()
        if value:
            filters[form_key] = value
    return filters


async def run_list(
    client: UmucyoClient,
    max_results: int,
    filters: dict,
    fetch_details: bool,
    sem: asyncio.Semaphore,
):
    collected = 0
    page_no = 1
    page_size = min(max_results, 50) or 50
    while collected < max_results:
        try:
            html = await client.fetch_list_page(page_no, page_size, filters)
            items, total_results, current_page, total_pages = parse_list_page(html)
        except (RuntimeError, RequestException, ConnectionError, OSError) as e:
            await Actor.push_data(
                extract_error("list", f"page={page_no}", "blocked_or_transient", repr(e))
            )
            break
        if not items:
            break

        remaining = max_results - collected
        items = items[:remaining]

        async def _one(item: dict) -> dict:
            fields = dict(item)
            if fetch_details:
                async with sem:
                    fields.update(await enrich_with_detail(client, item["detail_ref"]))
            return build_record("list", "S1-advertising-list-gu", fields)

        records = await asyncio.gather(*(_one(item) for item in items))
        for record in records:
            await Actor.push_data(record)
        collected += len(records)

        Actor.log.info(
            f"list: page {current_page}/{total_pages} ({total_results} total upstream) -- "
            f"pushed {collected}/{max_results}"
        )
        if current_page >= total_pages:
            break
        page_no += 1

    Actor.log.info(f"list: pushed {collected} tender notice(s)")


async def run_detail(client: UmucyoClient, detail_refs: list[str], sem: asyncio.Semaphore):
    async def _one(ref: str) -> dict:
        ref = ref.strip()
        if ref.count("|") != 2:
            return extract_error(
                "detail",
                ref,
                "invalid_detail_ref",
                f"Expected 'tendReferNo|tendStageCd|tendTypeCd', got {ref!r}",
            )
        async with sem:
            fields = await enrich_with_detail(client, ref)
        if "_detailError" in fields:
            return extract_error("detail", ref, "blocked_or_transient", fields["_detailError"])
        fields["detail_ref"] = ref
        return build_record("detail", "S1-advertising-detail-page", fields)

    records = await asyncio.gather(*(_one(ref) for ref in detail_refs))
    for record in records:
        await Actor.push_data(record)
    Actor.log.info(f"detail: pushed {len(records)} tender record(s)")


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode") or "list"
        if mode not in ("list", "detail"):
            raise input_error(f"Invalid mode {mode!r} -- expected 'list' or 'detail'.")

        max_results = min(int(input_data.get("maxResults", 50)), 2000)
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        detail_refs = list(input_data.get("detailRefs") or [])
        filters = _build_filters(input_data)

        if mode == "detail" and not detail_refs:
            raise input_error(
                "mode='detail' requires 'detailRefs' -- one or more 'tendReferNo|tendStageCd|tendTypeCd' "
                "strings, as emitted in the detail_ref field of mode='list' output."
            )

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        client = UmucyoClient(proxy_url)
        sem = asyncio.Semaphore(max_concurrency)
        try:
            Actor.log.info(f"Running mode={mode!r} maxResults={max_results} fetchDetails={fetch_details}")
            if mode == "list":
                await run_list(client, max_results, filters, fetch_details, sem)
            else:
                await run_detail(client, detail_refs, sem)
        finally:
            await client.close()
