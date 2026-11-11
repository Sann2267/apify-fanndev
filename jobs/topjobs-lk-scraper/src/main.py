import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import TopjobsClient
from src.constants import FUNCTIONAL_AREAS, PAGE_SIZE, SEARCH_URL
from src.extractor import (
    UnexpectedShape,
    build_detail_url,
    extract_detail_html,
    extract_error,
    extract_search_page,
    is_not_found,
    parse_job_params,
    wrap_detail,
    wrap_search_item,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

CHECKBOX_FILTERS = {
    "government": "chkGovt",
    "ngo": "chkNGO",
    "partTime": "chkParttime",
    "walkIn": "chkWalkin",
    "foreign": "chkForeign",
    "internship": "chkInternship",
}


def _build_search_params(keyword: str, functional_area: str | None, filters: dict, page_no: int) -> dict:
    params = {
        "FA": functional_area or "",
        "jst": "OPEN",
        "txtKeyWord": keyword or "",
        "pageNo": str(page_no),
    }
    for input_key, query_key in CHECKBOX_FILTERS.items():
        if filters.get(input_key):
            params[query_key] = "Y"
    return params


async def fetch_detail(client: TopjobsClient, jc: str, ac: str, ec: str, input_value: str) -> dict:
    url = build_detail_url(jc, ac, ec)
    r = await client.get(url)
    if r.status_code != 200:
        return extract_error(input_value, f"http_{r.status_code}")
    if is_not_found(str(r.url)):
        # topjobs.lk 302s an invalid/mismatched jc+ac+ec triple to
        # util/errorPage.jsp?errCode=601 instead of a 404 -- see extractor.is_not_found.
        return extract_error(input_value, "not_found")
    data = extract_detail_html(r.text)
    data["jc"], data["ac"], data["ec"] = jc, ac, ec
    data["detailUrl"] = url
    return wrap_detail(data, input_value)


async def run_search(
    keyword: str,
    functional_area: str | None,
    filters: dict,
    max_results: int,
    fetch_full_details: bool,
    max_concurrency: int,
    proxy_url_factory,
) -> list[dict]:
    input_value = f"keyword:{keyword or '(any)'}" if not functional_area else f"functionalArea:{functional_area}"
    client = TopjobsClient(proxy_url=await proxy_url_factory())
    try:
        all_summaries: list[dict] = []
        page_no = 1
        total = None
        while len(all_summaries) < max_results:
            r = await client.get(SEARCH_URL, params=_build_search_params(keyword, functional_area, filters, page_no))
            if r.status_code != 200:
                if not all_summaries:
                    return [extract_error(input_value, f"http_{r.status_code}")]
                break
            items, total = extract_search_page(r.text)
            if not items:
                break
            all_summaries.extend(items)
            if total is not None and page_no * PAGE_SIZE >= total:
                break
            if len(items) < PAGE_SIZE:
                break  # short page -- no more results even if `total` disagrees
            page_no += 1

        all_summaries = all_summaries[:max_results]
        Actor.log.info(f"mode=search input={input_value!r}: {len(all_summaries)} summary result(s), total reported by site={total}")

        if not fetch_full_details:
            return [wrap_search_item(it, input_value) for it in all_summaries]

        # Hydrate each summary into a full detail record, bounded concurrency.
        sem = asyncio.Semaphore(max_concurrency)
        records: list[dict | None] = [None] * len(all_summaries)

        async def _hydrate(i: int, summary: dict):
            async with sem:
                dclient = TopjobsClient(proxy_url=await proxy_url_factory())
                try:
                    records[i] = await fetch_detail(dclient, summary["jc"], summary["ac"], summary["ec"], input_value)
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


async def run_detail(job_url: str, proxy_url: str | None) -> dict:
    client = TopjobsClient(proxy_url=proxy_url)
    try:
        try:
            jc, ac, ec = parse_job_params(job_url)
        except ValueError as e:
            return extract_error(job_url, "invalid_input", str(e))
        return await fetch_detail(client, jc, ac, ec, job_url)
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(job_url, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "detail")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        functional_area = input_data.get("functionalArea") or None
        if functional_area and functional_area not in FUNCTIONAL_AREAS:
            raise input_error(f"Invalid functionalArea: {functional_area!r}. Must be one of {sorted(FUNCTIONAL_AREAS)}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        async def _proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "search":
            keyword = input_data.get("keyword", "")
            max_results = min(int(input_data.get("maxResults", 50)), 5000)
            fetch_full_details = bool(input_data.get("fetchFullDetails", True))
            filters = {k: bool(input_data.get(k)) for k in CHECKBOX_FILTERS}
            records = await run_search(keyword, functional_area, filters, max_results, fetch_full_details, max_concurrency, _proxy_url)
            Actor.log.info(f"mode=search: {len(records)} record(s) pushed")
            await Actor.push_data(records)
            return

        # mode == "detail"
        urls = list(input_data.get("jobUrls") or [])
        if input_data.get("jobUrl"):
            urls.insert(0, input_data["jobUrl"])
        if not urls:
            raise input_error("Provide 'jobUrl' or 'jobUrls' when mode is 'detail'.")
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_detail(u: str):
            async with sem:
                proxy_url = await _proxy_url()
                record = await run_detail(u, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=detail: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_detail(u) for u in urls))
