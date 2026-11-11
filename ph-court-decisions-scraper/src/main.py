import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import ELibraryClient
from src.constants import (
    ARCHIVE_FIRST_YEAR,
    DOCMONTH_URL,
    DTSEARCH_URL,
    KNOWN_BROKEN_INDEXES,
    MAX_LISTING_PAGES,
    MAX_SEARCH_PAGES,
    MONTHS,
    SEARCH_AUTO_STOP_LIMIT,
    SEARCH_CORPORA,
    SEARCH_PAGE_SIZE,
    SEARCH_TYPES,
    SHOWDOCS_URL,
)
from src.extractor import (
    BrokenSearchIndex,
    UnexpectedShape,
    extract_decision,
    extract_dtsearch_document,
    extract_error,
    extract_listing_page,
    extract_next_page_form,
    extract_search_page,
    merge_listing_and_decision,
    wrap,
)

log = logging.getLogger(__name__)

TRANSPORT_ERRORS = (RuntimeError, ConnectionError, RequestException, OSError)


def _search_payload(query: str, index_token: str, search_type: str) -> dict:
    """Every key here is one the portal's own search form submits; dtSearch
    rejects or misreads the request when the hidden defaults are omitted."""
    return {
        "cmd": "search",
        "request": query,
        "index": index_token,
        "searchType": search_type,
        "fuzziness": "3",
        "autoStopLimit": str(SEARCH_AUTO_STOP_LIMIT),
        "pageSize": str(SEARCH_PAGE_SIZE),
        "autoTermWeight": "1",
        "fileConditions": "",
        "booleanConditions": "",
    }


async def fetch_decision(client: ELibraryClient, doc_id: str) -> dict | None | str:
    """Returns the decision dict, None for a soft-404, or an error-kind
    string for a transport-level failure."""
    r = await client.get(f"{SHOWDOCS_URL}/{doc_id}")
    if r.status_code != 200:
        return f"http_{r.status_code}"
    return extract_decision(r.text, doc_id)


async def fetch_dtsearch_document(client: ELibraryClient, url: str, doc_id: str | None):
    r = await client.get(url)
    if r.status_code != 200:
        return f"http_{r.status_code}"
    return extract_dtsearch_document(r.text, url, doc_id)


async def _enrich_all(
    rows, max_concurrency, proxy_config, fetch_one, source_tag, fallback_source, input_value
):
    """Shared full-text enrichment fan-out. A failure on one document
    degrades that row to its summary form with a _warning; it never discards
    the row or sinks the run. `fallback_source` is passed explicitly rather
    than derived from `source_tag`, because a browse row that failed
    enrichment is still an S1-listing row -- deriving it would mislabel it
    S1-decision and make it indistinguishable from a decision-mode record."""
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict] = [None] * len(rows)  # type: ignore[list-item]

    async def _one(idx: int, row: dict):
        async with sem:
            proxy_url = await proxy_config.new_url() if proxy_config else None
            client = ELibraryClient(proxy_url=proxy_url)
            try:
                detail = await fetch_one(client, row)
                if isinstance(detail, dict):
                    results[idx] = wrap(
                        merge_listing_and_decision(row, detail), input_value, source_tag
                    )
                    return
                rec = wrap(row, input_value, fallback_source)
                rec["_warning"] = (
                    "full_text_unavailable" if detail is None else f"full_text_{detail}"
                )
                results[idx] = rec
            except TRANSPORT_ERRORS as e:
                rec = wrap(row, input_value, fallback_source)
                rec["_warning"] = "full_text_unavailable"
                rec["_errorDetail"] = repr(e)[:300]
                results[idx] = rec
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, r) for i, r in enumerate(rows)))
    return [r for r in results if r is not None]


async def run_search(
    query: str,
    corpus: str,
    search_type: str,
    max_results: int,
    fetch_full_text: bool,
    max_concurrency: int,
    proxy_config,
) -> list[dict]:
    input_value = f"q={query}|corpus={corpus}|type={search_type}"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ELibraryClient(proxy_url=proxy_url)
    collected: list[dict] = []
    total = None
    try:
        indexes = await client.search_indexes()
        index_token = indexes.get(corpus)
        if not index_token:
            return [extract_error(
                input_value, "unknown_corpus",
                f"Corpus {corpus!r} is not offered by the portal's search form. "
                f"Available: {sorted(indexes)}",
            )]

        payload = _search_payload(query, index_token, search_type)
        r = await client.post(DTSEARCH_URL, data=payload)
        if r.status_code != 200:
            return [extract_error(input_value, f"http_{r.status_code}", DTSEARCH_URL)]

        page = 1
        # dtSearch's relevance ordering is not perfectly stable between
        # requests, so a later page can re-serve a document an earlier page
        # already returned (confirmed live: page 2 of "negligence" repeated
        # two of page 1's documents). Dedupe on the engine's own document id
        # so the dataset never carries the same decision twice.
        seen: set[str] = set()
        while True:
            try:
                parsed = extract_search_page(r.text)
            except BrokenSearchIndex as e:
                return [extract_error(
                    input_value, "search_index_unavailable",
                    f"dtSearch cannot open the {corpus!r} index server-side "
                    f"(upstream defect, not an empty result set): {e}",
                )]
            total = parsed["total"] if total is None else total
            for row in parsed["rows"]:
                key = row.get("dtSearchDocId") or row.get("documentUrl")
                if key in seen:
                    continue
                seen.add(key)
                collected.append(row)
            if len(collected) >= max_results or not parsed["rows"]:
                break

            next_form = extract_next_page_form(r.text)
            if not next_form:
                break
            page += 1
            if page > MAX_SEARCH_PAGES:
                break
            r = await client.post(DTSEARCH_URL, data=next_form)
            if r.status_code != 200:
                break

    except (UnexpectedShape, BrokenSearchIndex):
        raise
    except TRANSPORT_ERRORS as e:
        if not collected:
            return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await client.close()
    collected = collected[:max_results]

    if not collected:
        return [extract_error(
            input_value, "no_results",
            f"dtSearch returned no documents for query={query!r} in corpus={corpus!r} "
            f"(reported total: {total})",
        )]

    if not fetch_full_text:
        return [wrap(row, input_value, "S1-search") for row in collected]

    async def _fetch(client: ELibraryClient, row: dict):
        return await fetch_dtsearch_document(client, row["documentUrl"], row.get("dtSearchDocId"))

    return await _enrich_all(
        collected, max_concurrency, proxy_config, _fetch, "S2-search", "S1-search", input_value
    )


async def run_browse(
    from_year: int,
    to_year: int,
    max_results: int,
    fetch_full_text: bool,
    max_concurrency: int,
    proxy_config,
) -> list[dict]:
    input_value = f"years={from_year}-{to_year}"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = ELibraryClient(proxy_url=proxy_url)
    collected: list[dict] = []
    try:
        # Newest first, matching how the portal itself presents the archive.
        for year in range(to_year, from_year - 1, -1):
            for month in reversed(MONTHS):
                page = 1
                while page <= MAX_LISTING_PAGES:
                    r = await client.get(f"{DOCMONTH_URL}/{month}/{year}/{page}")
                    if r.status_code != 200:
                        break
                    rows = extract_listing_page(r.text)
                    if not rows:
                        break  # the portal prints no next-page links; empty == end of month
                    for row in rows:
                        row["month"] = month
                        row["year"] = year
                    collected.extend(rows)
                    if len(collected) >= max_results:
                        break
                    page += 1
                if len(collected) >= max_results:
                    break
            if len(collected) >= max_results:
                break
    except UnexpectedShape:
        raise
    except TRANSPORT_ERRORS as e:
        if not collected:
            return [extract_error(input_value, "blocked_or_transient", repr(e))]
    finally:
        await client.close()
    collected = collected[:max_results]

    if not collected:
        return [extract_error(
            input_value, "no_results",
            f"No decisions listed for years {from_year}-{to_year}",
        )]

    if not fetch_full_text:
        return [wrap(row, input_value, "S1-listing") for row in collected]

    async def _fetch(client: ELibraryClient, row: dict):
        return await fetch_decision(client, row["docId"])

    return await _enrich_all(
        collected, max_concurrency, proxy_config, _fetch, "S2-decision", "S1-listing", input_value
    )


async def run_decision(doc_id: str, proxy_url: str | None) -> dict:
    client = ELibraryClient(proxy_url=proxy_url)
    try:
        detail = await fetch_decision(client, doc_id)
        if isinstance(detail, str):
            return extract_error(doc_id, detail, f"{SHOWDOCS_URL}/{doc_id}")
        if detail is None:
            return extract_error(
                doc_id, "decision_not_found",
                f"HTTP 200 but no document body for docId={doc_id!r}",
            )
        return wrap(detail, doc_id, "S1-decision")
    except TRANSPORT_ERRORS as e:
        return extract_error(doc_id, "blocked_or_transient", repr(e))
    finally:
        await client.close()


def _normalise_doc_ids(raw_values: list) -> list[str]:
    """Accepts bare ids ("70008") and full portal URLs alike, since that is
    what a user copying out of the browser will paste."""
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        digits = text.rstrip("/").split("/")[-1] if "/" in text else text
        digits = digits.strip()
        if not digits.isdigit():
            raise ValueError(
                f"Invalid docId {value!r}: expected the numeric document id from a "
                "/thebookshelf/showdocs/1/<id> URL, e.g. \"70008\"."
            )
        if digits not in seen:
            seen.add(digits)
            out.append(digits)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        valid_modes = ("search", "browse", "decision")
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        max_results = int(input_data.get("maxResults", 50))
        fetch_full_text = bool(input_data.get("fetchFullText", False))

        if mode == "search":
            query = (input_data.get("searchPhrase") or "").strip()
            if not query:
                raise ValueError("Provide 'searchPhrase' when mode is 'search'.")
            corpus = input_data.get("searchCorpus") or "sc_decision"
            if corpus not in SEARCH_CORPORA:
                raise ValueError(f"Invalid searchCorpus: {corpus!r}. Must be one of {SEARCH_CORPORA}.")
            if corpus in KNOWN_BROKEN_INDEXES:
                Actor.log.warning(
                    f"searchCorpus={corpus!r} was unreadable server-side at recon time "
                    "(dtSearch '$E 0001 Unable to access index'). If it is still broken "
                    "this run emits a search_index_unavailable diagnostic rather than a "
                    "silent zero."
                )
            search_type = input_data.get("searchType") or "anywords"
            if search_type not in SEARCH_TYPES:
                raise ValueError(f"Invalid searchType: {search_type!r}. Must be one of {SEARCH_TYPES}.")

            records = await run_search(
                query, corpus, search_type, max_results,
                fetch_full_text, max_concurrency, proxy_config,
            )
            Actor.log.info(
                f"mode=search query={query!r} corpus={corpus!r} type={search_type!r}: "
                f"{len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        if mode == "browse":
            to_year = int(input_data.get("toYear") or 2026)
            from_year = int(input_data.get("fromYear") or to_year)
            if from_year > to_year:
                raise ValueError(f"fromYear ({from_year}) must not be after toYear ({to_year}).")
            if from_year < ARCHIVE_FIRST_YEAR:
                raise ValueError(
                    f"fromYear ({from_year}) precedes the archive, which starts at "
                    f"{ARCHIVE_FIRST_YEAR}."
                )

            records = await run_browse(
                from_year, to_year, max_results,
                fetch_full_text, max_concurrency, proxy_config,
            )
            Actor.log.info(
                f"mode=browse years={from_year}-{to_year}: {len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        # mode == "decision"
        doc_ids = _normalise_doc_ids(list(input_data.get("docIds") or []))
        if not doc_ids:
            raise ValueError("Provide 'docIds' (e.g. [\"70008\"]) when mode is 'decision'.")
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(doc_id: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_decision(doc_id, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=decision: {len(doc_ids)} document id(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(d) for d in doc_ids))
