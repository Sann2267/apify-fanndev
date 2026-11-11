import asyncio
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import TopCVClient
from src.constants import SITE_BASE
from src.extractor import (
    UnexpectedShape,
    build_search_url,
    extract_detail_jsonld,
    extract_error,
    extract_search_page,
    is_not_found_url,
    parse_job_id_from_url,
    resolve_city,
    wrap_detail,
    wrap_search_item,
)
from src.input_errors import input_error

_BARE_ID_RE = re.compile(r"^\d+$")


def parse_job_id(value: str) -> str:
    """Accepts a bare numeric job ID or a full topcv.vn/viec-lam/.../<id>.html URL."""
    value = value.strip()
    if _BARE_ID_RE.match(value):
        return value
    job_id = parse_job_id_from_url(value)
    if job_id:
        return job_id
    raise ValueError(f"Could not parse a job ID out of {value!r}.")


async def fetch_detail(client: TopCVClient, job_id: str, input_value: str) -> dict:
    url = f"{SITE_BASE}/viec-lam/x/{job_id}.html"
    r = await client.get(url)
    if r.status_code != 200:
        return extract_error(input_value, f"http_{r.status_code}")
    if is_not_found_url(str(r.url)):
        return extract_error(input_value, "not_found")
    data = extract_detail_jsonld(r.text)
    if data is None:
        return extract_error(input_value, "not_found")
    return wrap_detail(data, input_value)


async def run_search(
    keyword: str | None,
    city: str | None,
    max_results: int,
    fetch_full_details: bool,
    max_concurrency: int,
    proxy_url_factory,
) -> list[dict]:
    input_value = f"keyword:{keyword or '(any)'} city:{city or '(any)'}"
    city_resolved = None
    if city:
        try:
            city_resolved = resolve_city(city)
        except ValueError as e:
            return [extract_error(input_value, "invalid_city", str(e))]

    client = TopCVClient(proxy_url=await proxy_url_factory())
    try:
        all_summaries: list[dict] = []
        page = 1
        total_pages = None
        while len(all_summaries) < max_results:
            url = build_search_url(keyword, city_resolved, page)
            r = await client.get(url)
            if r.status_code != 200:
                if not all_summaries:
                    return [extract_error(input_value, f"http_{r.status_code}")]
                break
            items, current_page, total_pages = extract_search_page(r.text)
            if not items:
                break
            all_summaries.extend(items)
            if current_page >= total_pages:
                break
            page += 1

        all_summaries = all_summaries[:max_results]
        Actor.log.info(f"mode=search keyword={keyword!r} city={city!r}: {len(all_summaries)} summary result(s), total_pages reported by site={total_pages}")

        if not fetch_full_details:
            return [wrap_search_item(it, input_value) for it in all_summaries]

        # Hydrate each summary into a full detail record via its own
        # JSON-LD JobPosting, bounded concurrency.
        sem = asyncio.Semaphore(max_concurrency)
        records: list[dict | None] = [None] * len(all_summaries)

        async def _hydrate(i: int, summary: dict):
            async with sem:
                dclient = TopCVClient(proxy_url=await proxy_url_factory())
                try:
                    try:
                        record = await fetch_detail(dclient, summary["job_id"], input_value)
                    except (RuntimeError, ConnectionError, RequestException):
                        # One job's detail fetch being blocked/transient-failed
                        # (e.g. a rotated proxy IP getting rate-limited) must
                        # NOT take down the whole batch via gather -- fall
                        # back to that job's own search summary instead.
                        record = {"_source": "none"}
                    if record.get("_source") == "none":
                        # Detail lookup failed (e.g. delisted between search
                        # and hydration, or blocked/transient) -- fall back to
                        # the search summary rather than dropping the result.
                        record = {**wrap_search_item(summary, input_value), "_warning": "detail_fetch_failed_used_search_summary"}
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
    client = TopCVClient(proxy_url=proxy_url)
    try:
        try:
            job_id = parse_job_id(id_or_url)
        except ValueError as e:
            return extract_error(id_or_url, "invalid_input", str(e))
        return await fetch_detail(client, job_id, id_or_url)
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

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        async def _proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "search":
            keyword = input_data.get("keyword") or None
            city = input_data.get("city") or None
            max_results = min(int(input_data.get("maxResults", 50)), 2000)
            fetch_full_details = bool(input_data.get("fetchFullDetails", True))
            records = await run_search(keyword, city, max_results, fetch_full_details, max_concurrency, _proxy_url)
            Actor.log.info(f"mode=search: {len(records)} record(s) pushed")
            await Actor.push_data(records)
            return

        # mode == "detail"
        ids = list(input_data.get("jobIds") or [])
        if input_data.get("jobId"):
            ids.insert(0, input_data["jobId"])
        if not ids:
            raise input_error("Provide 'jobId' or 'jobIds' when mode is 'detail'.")
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
