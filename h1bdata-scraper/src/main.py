import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import H1BDataClient
from src.constants import DETAIL_URL, SEARCH_URL, VALID_YEARS
from src.extractor import (
    UnexpectedShape,
    extract_case_detail,
    extract_error,
    extract_search_page,
    wrap,
)

log = logging.getLogger(__name__)


async def run_search(
    employer: str,
    job_title: str,
    city: str,
    year: str,
    max_results: int,
    fetch_case_details: bool,
    max_concurrency: int,
    proxy_config,
) -> list[dict]:
    input_value = f"em={employer}|job={job_title}|city={city}|year={year}"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = H1BDataClient(proxy_url=proxy_url)
    try:
        params = {"em": employer, "job": job_title, "city": city, "year": year}
        r = await client.get(SEARCH_URL, params=params)
        if r.status_code != 200:
            return [extract_error(input_value, f"http_{r.status_code}", SEARCH_URL)]
        # Since Oct 2026 the site withholds its most-searched sponsors (Google,
        # Meta, Amazon, Apple ...): HTTP 200 with a 0-byte body, or the page
        # header with no results table. Deterministic, not a block -- retrying
        # does not help, so report it instead of treating it as a shape change.
        if not r.content or (b'id="myTable"' not in r.content and b"H1B Salary" in r.content):
            return [extract_error(
                input_value, "upstream_withheld",
                "h1bdata.info returned no results table for this query -- the site currently withholds "
                "results for some of the largest sponsors (e.g. Google, Meta, Amazon, Apple).",
            )]
        rows = extract_search_page(r.text)
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if not rows:
        return [extract_error(
            input_value, "no_results",
            f"No H1B filings matched employer={employer!r} jobTitle={job_title!r} city={city!r} year={year!r}",
        )]

    rows = rows[:max_results]

    if not fetch_case_details:
        return [wrap(row, input_value, "S1-search-summary") for row in rows]

    # Enrichment pass: dedupe by caseId (search results can repeat the same
    # case across cities/positions) and fetch details.php with bounded
    # concurrency, then merge back onto every row that referenced it.
    unique_ids = sorted({row["caseId"] for row in rows if row.get("caseId")})
    detail_cache: dict[str, dict | None] = {}
    sem = asyncio.Semaphore(max_concurrency)

    async def _fetch_detail(case_id: str):
        async with sem:
            d_proxy_url = await proxy_config.new_url() if proxy_config else None
            d_client = H1BDataClient(proxy_url=d_proxy_url)
            try:
                dr = await d_client.get(DETAIL_URL, params={"id": case_id})
                detail_cache[case_id] = extract_case_detail(dr.text) if dr.status_code == 200 else None
            except (RuntimeError, ConnectionError, RequestException):
                detail_cache[case_id] = None
            finally:
                await d_client.close()

    await asyncio.gather(*(_fetch_detail(cid) for cid in unique_ids))

    results = []
    for row in rows:
        case_id = row.get("caseId")
        detail = detail_cache.get(case_id) if case_id else None
        if detail:
            results.append(wrap({**row, **detail}, input_value, "S2-detail"))
        else:
            rec = wrap(row, input_value, "S1-search-summary")
            rec["_warning"] = "case_detail_unavailable"
            results.append(rec)
    return results


async def run_case_detail(case_id: str, proxy_url: str | None) -> dict:
    client = H1BDataClient(proxy_url=proxy_url)
    try:
        r = await client.get(DETAIL_URL, params={"id": case_id})
        if r.status_code != 200:
            return extract_error(case_id, f"http_{r.status_code}", DETAIL_URL)
        detail = extract_case_detail(r.text)
        if detail is None:
            return extract_error(case_id, "case_not_found", f"HTTP 200 but no record table for id={case_id!r}")
        return wrap(detail, case_id, "S1-detail")
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(case_id, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "caseDetail")
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        if mode == "search":
            employer = (input_data.get("employer") or "").strip()
            job_title = (input_data.get("jobTitle") or "").strip()
            city = (input_data.get("city") or "").strip()
            year = input_data.get("year") or "All Years"
            if year not in VALID_YEARS:
                raise ValueError(f"Invalid year: {year!r}. Must be one of {VALID_YEARS}.")
            if not (employer or job_title or city):
                raise ValueError(
                    "Provide at least one of 'employer', 'jobTitle', or 'city' for mode='search' -- "
                    "an unfiltered query against the full multi-year H1B dataset is not supported "
                    "(the response would be an unbounded multi-hundred-MB HTML page)."
                )
            max_results = int(input_data.get("maxResults", 200))
            fetch_case_details = bool(input_data.get("fetchCaseDetails", False))

            records = await run_search(
                employer, job_title, city, year, max_results, fetch_case_details, max_concurrency, proxy_config,
            )
            Actor.log.info(
                f"mode=search employer={employer!r} jobTitle={job_title!r} city={city!r} year={year!r}: "
                f"{len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        # mode == "caseDetail"
        case_ids = list(input_data.get("caseIds") or [])
        if not case_ids:
            raise ValueError("Provide 'caseIds' (e.g. [\"I-200-21027-037298\"]) when mode is 'caseDetail'.")
        seen: set[str] = set()
        case_ids = [c for c in case_ids if c and not (c in seen or seen.add(c))]
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_detail(cid: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_case_detail(cid, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=caseDetail: {len(case_ids)} case id(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_detail(c) for c in case_ids))
