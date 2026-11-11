import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import KarirClient
from src.constants import DETAIL_URL, PAGE_SIZE, SEARCH_URL, SORT_ORDER_VALUES
from src.extractor import (
    UnexpectedShape,
    extract_detail,
    extract_error,
    extract_search_page,
    is_disallowed,
    parse_opportunity_id,
    wrap_detail,
    wrap_search_item,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _build_search_body(keyword: str, sort_order: str | None, filters: dict, limit: int, offset: int) -> dict:
    body = {
        "keyword": keyword or "",
        "locale": "id",
        "limit": limit,
        "offset": offset,
    }
    if sort_order:
        body["sort_order"] = sort_order
    # Optional advanced filters -- raw passthrough, only included if the
    # caller actually supplied them. IDs (location_ids, job_function_ids,
    # industry_ids, degree_ids) come from karir.com's own filter UI; this
    # actor does not resolve human-readable names to IDs for these (see
    # CRAWLING_METHOD.md -- `v1/location/search` does not filter by
    # keyword server-side, so no reliable name->ID lookup could be built).
    for key in (
        "location_ids",
        "company_ids",
        "industry_ids",
        "job_function_ids",
        "degree_ids",
        "min_salary",
        "max_salary",
        "level",
        "workplace",
    ):
        if filters.get(key) not in (None, "", []):
            body[key] = filters[key]
    return body


async def fetch_detail(client: KarirClient, opportunity_id: str, input_value: str, is_urgent: bool | None = None) -> dict:
    if is_disallowed(opportunity_id):
        return extract_error(input_value, "disallowed_by_robots_txt", f"opportunity {opportunity_id} is explicitly disallowed in karir.com/robots.txt")
    r = await client.post_json(DETAIL_URL, {"opportunity_id": int(opportunity_id)})
    if r.status_code == 400:
        # The API uses HTTP 400 + {"message": ["Invalid Opportunity"]} for a
        # nonexistent/expired-and-purged ID rather than a literal 404 --
        # confirmed live. Surface it as a normal not-found, not a generic error.
        try:
            msg = r.json().get("message")
        except Exception:  # noqa: BLE001 -- body isn't JSON, fall through to generic error below
            msg = None
        if msg and any("Invalid Opportunity" in m for m in msg):
            return extract_error(input_value, "not_found")
    if r.status_code != 200:
        return extract_error(input_value, f"http_{r.status_code}")
    data = extract_detail(r.json())
    if data is None:
        return extract_error(input_value, "not_found")
    return wrap_detail(data, input_value, is_urgent)


async def run_search(
    keyword: str,
    sort_order: str | None,
    filters: dict,
    max_results: int,
    fetch_full_details: bool,
    max_concurrency: int,
    proxy_url_factory,
) -> list[dict]:
    input_value = f"keyword:{keyword or '(any)'}"
    client = KarirClient(proxy_url=await proxy_url_factory())
    try:
        all_summaries: list[dict] = []
        offset = 0
        total = None
        while len(all_summaries) < max_results:
            limit = min(PAGE_SIZE, max_results - len(all_summaries))
            body = _build_search_body(keyword, sort_order, filters, limit, offset)
            r = await client.post_json(SEARCH_URL, body)
            if r.status_code != 200:
                if not all_summaries:
                    return [extract_error(input_value, f"http_{r.status_code}")]
                break
            items, total = extract_search_page(r.json())
            if not items:
                break
            all_summaries.extend(items)
            offset += len(items)
            if total is not None and offset >= total:
                break
            if len(items) < limit:
                break  # short page -- no more results even if `total` disagrees

        all_summaries = all_summaries[:max_results]
        Actor.log.info(f"mode=search keyword={keyword!r}: {len(all_summaries)} summary result(s), total reported by API={total}")

        if not fetch_full_details:
            return [wrap_search_item(it, input_value) for it in all_summaries]

        # Hydrate each summary into a full detail record, bounded concurrency.
        sem = asyncio.Semaphore(max_concurrency)
        records: list[dict | None] = [None] * len(all_summaries)

        async def _hydrate(i: int, summary: dict):
            async with sem:
                dclient = KarirClient(proxy_url=await proxy_url_factory())
                try:
                    oid = str(summary.get("id"))
                    record = await fetch_detail(dclient, oid, input_value, is_urgent=summary.get("is_urgent"))
                    records[i] = record
                finally:
                    await dclient.close()

        await asyncio.gather(*(_hydrate(i, s) for i, s in enumerate(all_summaries)))
        return [r for r in records if r is not None]
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail(id_or_url: str, proxy_url: str | None) -> dict:
    client = KarirClient(proxy_url=proxy_url)
    try:
        try:
            opportunity_id = parse_opportunity_id(id_or_url)
        except ValueError as e:
            return extract_error(id_or_url, "invalid_input", str(e))
        return await fetch_detail(client, opportunity_id, id_or_url)
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(id_or_url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "detail")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        sort_order = input_data.get("sortOrder")
        if sort_order and sort_order not in SORT_ORDER_VALUES:
            raise input_error(f"Invalid sortOrder: {sort_order!r}. Must be one of {SORT_ORDER_VALUES}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        async def _proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "search":
            keyword = input_data.get("keyword", "")
            max_results = min(int(input_data.get("maxResults", 50)), 2000)
            fetch_full_details = bool(input_data.get("fetchFullDetails", True))
            filters = {
                "location_ids": input_data.get("locationIds"),
                "company_ids": input_data.get("companyIds"),
                "industry_ids": input_data.get("industryIds"),
                "job_function_ids": input_data.get("jobFunctionIds"),
                "degree_ids": input_data.get("degreeIds"),
                "min_salary": input_data.get("minSalary"),
                "max_salary": input_data.get("maxSalary"),
                "level": input_data.get("level"),
                "workplace": input_data.get("workplace"),
            }
            records = await run_search(keyword, sort_order, filters, max_results, fetch_full_details, max_concurrency, _proxy_url)
            Actor.log.info(f"mode=search: {len(records)} record(s) pushed")
            await Actor.push_data(records)
            return

        # mode == "detail"
        ids = list(input_data.get("opportunityIds") or [])
        if input_data.get("opportunityId"):
            ids.insert(0, input_data["opportunityId"])
        if not ids:
            raise input_error("Provide 'opportunityId' or 'opportunityIds' when mode is 'detail'.")
        seen = set()
        ids = [i for i in ids if not (i in seen or seen.add(i))]

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_detail(i: str):
            async with sem:
                proxy_url = await _proxy_url()
                record = await run_detail(i, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=detail: {len(ids)} id(s)/url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_detail(i) for i in ids))
