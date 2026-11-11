import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ELitigationClient
from src.constants import (
    COURT_FILTER,
    JUDGMENT_URL,
    MAX_PAGE_SANITY_CAP,
    SEARCH_URL,
    SORT_FIELDS,
)
from src.extractor import (
    UnexpectedShape,
    extract_error,
    extract_judgment,
    extract_search_page,
    merge_listing_and_judgment,
    wrap,
)

log = logging.getLogger(__name__)


def _search_params(page: int, search_phrase: str, year: str, sort_by: str, ascending: bool) -> dict:
    """The listing is a plain GET form -- every one of these keys is
    required by the endpoint even when unused (it echoes them back into
    its own pagination links)."""
    params = {
        "Filter": COURT_FILTER,
        "YearOfDecision": year,
        "SortBy": sort_by,
        "CurrentPage": str(page),
        "SortAscending": "True" if ascending else "False",
        "PageSize": "0",
        "Verbose": "False",
        "SearchQueryTime": "0",
        "SearchTotalHits": "0",
        "SearchMode": "True",
        "SpanMultiplePages": "False",
    }
    if search_phrase:
        params["SearchPhrase"] = search_phrase
    return params


async def fetch_one_judgment(client: ELitigationClient, judgment_id: str) -> dict | None | str:
    """Returns the judgment dict, None for a soft-404, or an error-kind
    string for a transport-level failure."""
    r = await client.get(f"{JUDGMENT_URL}/{judgment_id}")
    if r.status_code != 200:
        return f"http_{r.status_code}"
    return extract_judgment(r.text, judgment_id)


async def run_search(
    search_phrase: str,
    year: str,
    sort_by: str,
    ascending: bool,
    max_results: int,
    fetch_full_text: bool,
    max_concurrency: int,
    proxy_config,
) -> list[dict]:
    input_value = f"q={search_phrase}|year={year}|sort={sort_by}"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ELitigationClient(proxy_url=proxy_url)
    collected: list[dict] = []
    try:
        page = 1
        while len(collected) < max_results:
            r = await client.get(SEARCH_URL, params=_search_params(page, search_phrase, year, sort_by, ascending))
            if r.status_code != 200:
                if collected:
                    break  # partial results already gathered -- return them rather than discarding
                return [extract_error(input_value, f"http_{r.status_code}", SEARCH_URL)]

            rows = extract_search_page(r.text)
            if not rows:
                break  # legitimately past the end of the result set
            collected.extend(rows)
            page += 1
            if page > MAX_PAGE_SANITY_CAP:
                break
        collected = collected[:max_results]
    except UnexpectedShape:
        raise
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await client.close()

    if not collected:
        return [extract_error(
            input_value, "no_results",
            f"No judgments matched searchPhrase={search_phrase!r} year={year!r}",
        )]

    if not fetch_full_text:
        return [wrap(row, input_value, "S1-listing") for row in collected]

    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict] = [None] * len(collected)  # type: ignore[list-item]

    async def _enrich(idx: int, row: dict):
        async with sem:
            judgment_id = row.get("judgmentId")
            if not judgment_id:
                rec = wrap(row, input_value, "S1-listing")
                rec["_warning"] = "missing_judgment_id"
                results[idx] = rec
                return
            d_proxy_url = await proxy_config.new_url() if proxy_config else None
            d_client = ELitigationClient(proxy_url=d_proxy_url)
            try:
                detail = await fetch_one_judgment(d_client, judgment_id)
                if isinstance(detail, dict):
                    results[idx] = wrap(
                        merge_listing_and_judgment(row, detail), input_value, "S2-judgment"
                    )
                    return
                rec = wrap(row, input_value, "S1-listing")
                rec["_warning"] = "full_text_unavailable" if detail is None else f"full_text_{detail}"
                results[idx] = rec
            except (RuntimeError, ConnectionError, RequestException) as e:
                rec = wrap(row, input_value, "S1-listing")
                rec["_warning"] = "full_text_unavailable"
                rec["_errorDetail"] = repr(e)[:300]
                results[idx] = rec
            finally:
                await d_client.close()

    await asyncio.gather(*(_enrich(i, row) for i, row in enumerate(collected)))
    return [r for r in results if r is not None]


async def run_judgment(judgment_id: str, proxy_url: str | None) -> dict:
    client = ELitigationClient(proxy_url=proxy_url)
    try:
        detail = await fetch_one_judgment(client, judgment_id)
        if isinstance(detail, str):
            return extract_error(judgment_id, detail, f"{JUDGMENT_URL}/{judgment_id}")
        if detail is None:
            return extract_error(
                judgment_id, "judgment_not_found",
                f"HTTP 200 but no judgment body for id={judgment_id!r} "
                "(elitigation.sg soft-404s unknown ids)",
            )
        return wrap(detail, judgment_id, "S1-judgment")
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(judgment_id, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "judgment")
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        if mode == "search":
            search_phrase = (input_data.get("searchPhrase") or "").strip()
            year = str(input_data.get("year") or "All").strip() or "All"
            sort_by = input_data.get("sortBy") or "DateOfDecision"
            if sort_by not in SORT_FIELDS:
                raise ValueError(f"Invalid sortBy: {sort_by!r}. Must be one of {SORT_FIELDS}.")
            ascending = bool(input_data.get("sortAscending", False))
            max_results = int(input_data.get("maxResults", 50))
            fetch_full_text = bool(input_data.get("fetchFullText", False))

            records = await run_search(
                search_phrase, year, sort_by, ascending, max_results,
                fetch_full_text, max_concurrency, proxy_config,
            )
            Actor.log.info(
                f"mode=search searchPhrase={search_phrase!r} year={year!r} sortBy={sort_by!r}: "
                f"{len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        # mode == "judgment"
        judgment_ids = list(input_data.get("judgmentIds") or [])
        if not judgment_ids:
            raise ValueError("Provide 'judgmentIds' (e.g. [\"2026_SGHC_175\"]) when mode is 'judgment'.")
        seen: set[str] = set()
        judgment_ids = [j.strip() for j in judgment_ids if j and j.strip()]
        judgment_ids = [j for j in judgment_ids if not (j in seen or seen.add(j))]
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(jid: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_judgment(jid, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=judgment: {len(judgment_ids)} judgment id(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(j) for j in judgment_ids))
