import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BolpatraClient, FetchFailed
from src.constants import PROCUREMENT_CATEGORY_MAP, PROCUREMENT_METHOD_MAP
from src.extractor import (
    TENDER_ID_IN_URL_RE,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_detail,
    parse_listing,
)
from src.input_errors import input_error


def _normalize_tender_id(value) -> str | None:
    """Accepts a bare numeric id (str/int) or a full detail URL and returns
    the numeric id as a string, or None if nothing usable was found."""
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return s
    m = TENDER_ID_IN_URL_RE.search(s)
    return m.group(1) if m else None


async def run_list(input_data: dict, proxy_url_fn) -> list[dict]:
    keyword = (input_data.get("keyword") or "").strip()
    category = input_data.get("procurementCategory") or "all"
    method = input_data.get("procurementMethod") or "all"
    entity_name = (input_data.get("publicEntityName") or "").strip()
    max_results = int(input_data.get("maxResults", 30))
    max_results = max(1, min(max_results, 30))

    if category not in PROCUREMENT_CATEGORY_MAP:
        raise ValueError(f"procurementCategory must be one of {list(PROCUREMENT_CATEGORY_MAP)}, got {category!r}")
    if method not in PROCUREMENT_METHOD_MAP:
        raise ValueError(f"procurementMethod must be one of {list(PROCUREMENT_METHOD_MAP)}, got {method!r}")

    has_filters = bool(keyword or entity_name or category != "all" or method != "all")
    query_label = (
        "latest" if not has_filters else f"search:title={keyword!r},category={category},method={method},entity={entity_name!r}"
    )

    proxy_url = await proxy_url_fn()
    client = BolpatraClient(proxy_url)
    try:
        if not has_filters:
            # No filters at all -- use the dedicated "recent opportunities"
            # dashboard endpoint, which reliably returns the 30 freshest
            # tenders with zero session/priming needed (see constants.py).
            html_text = await client.fetch_latest()
        else:
            form_fields = {
                "bidSearchTO.title": keyword,
                "bidSearchTO.procurementCategory": PROCUREMENT_CATEGORY_MAP[category],
                "bidSearchTO.procurementMethod": PROCUREMENT_METHOD_MAP[method],
            }
            if entity_name:
                resolved = await client.resolve_entity_id(entity_name)
                if resolved is None:
                    Actor.log.warning(f"No public-entity match for {entity_name!r} -- searching without the entity filter.")
                else:
                    entity_id, matched_name = resolved
                    form_fields["bidSearchTO.publicEntity"] = entity_id
                    Actor.log.info(f"Resolved publicEntityName {entity_name!r} -> id={entity_id} ({matched_name!r}).")
            html_text = await client.search(form_fields)

        parsed = parse_listing(html_text)  # raises UnexpectedShape -- must NOT be swallowed, per project convention
        total_returned = len(parsed["rows"])
        rows = parsed["rows"][:max_results]
        if len(rows) < total_returned:
            Actor.log.info(f"{query_label}: kept {len(rows)} of {total_returned} rows this query returned (maxResults cap).")
        if not rows:
            Actor.log.info(f"{query_label}: matched 0 tenders.")
        return [build_list_record(row, parsed["totalAvailable"], total_returned, query_label) for row in rows]
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError/RequestException does not
        # inherit from Python's builtin ConnectionError -- both listed, per
        # this portfolio's Babak 22b fix.
        return [build_error_record(query_label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail(tender_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(tender_ids)

    async def _one(i: int, tender_id: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            client = BolpatraClient(proxy_url)
            try:
                html_text = await client.fetch_detail(tender_id)
                parsed = parse_detail(html_text)  # raises UnexpectedShape -- fail loud, not swallowed
                results[i] = build_detail_record(tender_id, parsed)
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                results[i] = build_error_record(tender_id, "blocked_or_transient", repr(e))
            finally:
                await client.close()

    await asyncio.gather(*(_one(i, tid) for i, tid in enumerate(tender_ids)))
    return [r for r in results if r is not None]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "list")
        if mode not in ("list", "detail"):
            raise input_error(f"mode must be 'list' or 'detail', got {mode!r}")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "list":
            Actor.log.info("mode=list")
            records = await run_list(input_data, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("tenderId"):
            raw_ids.append(input_data["tenderId"])
        raw_ids.extend(input_data.get("tenderIds") or [])
        tender_ids = []
        seen = set()
        for raw in raw_ids:
            tid = _normalize_tender_id(raw)
            if tid and tid not in seen:
                seen.add(tid)
                tender_ids.append(tid)
        if not tender_ids:
            raise input_error("Provide 'tenderId' or a non-empty 'tenderIds' array (numeric IDs or detail URLs).")

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        max_concurrency = max(1, min(max_concurrency, 10))

        Actor.log.info(f"mode=detail {len(tender_ids)} tenderId(s), maxConcurrency={max_concurrency}")
        records = await run_detail(tender_ids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
