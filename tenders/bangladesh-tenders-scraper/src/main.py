import asyncio
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import EprocureClient, FetchFailed
from src.constants import PROCUREMENT_NATURE_MAP
from src.extractor import (
    build_awarded_record,
    build_detail_record,
    build_error_record,
    build_list_record,
    parse_awarded_fragment,
    parse_detail,
    parse_list_fragment,
)
from src.input_errors import input_error

TENDER_ID_IN_URL_RE = re.compile(r"[?&]id=(\d+)")


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
    nature = input_data.get("procurementNature") or "all"
    max_results = int(input_data.get("maxResults", 30))
    max_results = max(1, min(max_results, 100))

    if nature not in PROCUREMENT_NATURE_MAP:
        raise ValueError(f"procurementNature must be one of {list(PROCUREMENT_NATURE_MAP)}, got {nature!r}")

    if keyword and nature != "all":
        Actor.log.warning(
            "eprocure.gov.bd silently ignores procurementNature whenever keyword is also set (confirmed server-side "
            "quirk, see CRAWLING_METHOD.md) -- this query will be keyword-only."
        )
    query_label = "latest" if not (keyword or nature != "all") else f"search:keyword={keyword!r},procurementNature={nature}"

    client = EprocureClient(await proxy_url_fn())
    try:
        html_text = await client.fetch_list(keyword, PROCUREMENT_NATURE_MAP[nature], page_no=1, size=max_results)
        parsed = parse_list_fragment(html_text)  # raises UnexpectedShape -- must NOT be swallowed, per project convention
        rows = parsed["rows"][:max_results]
        if not rows:
            Actor.log.info(f"{query_label}: matched 0 live tenders.")
        return [build_list_record(row, parsed["totalPages"], query_label) for row in rows]
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own ConnectionError/RequestException does not
        # inherit from Python's builtin ConnectionError -- both listed, per
        # this portfolio's Babak 22b fix.
        return [build_error_record(query_label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_awarded(input_data: dict, proxy_url_fn) -> list[dict]:
    keyword = (input_data.get("keyword") or "").strip()
    max_results = int(input_data.get("maxResults", 30))
    max_results = max(1, min(max_results, 100))
    query_label = "latest" if not keyword else f"search:keyword={keyword!r}"

    client = EprocureClient(await proxy_url_fn())
    try:
        html_text = await client.fetch_awarded(keyword, page_no=1, size=max_results)
        parsed = parse_awarded_fragment(html_text)  # raises UnexpectedShape -- must NOT be swallowed
        rows = parsed["rows"][:max_results]
        if not rows:
            Actor.log.info(f"{query_label}: matched 0 awarded contracts.")
        return [build_awarded_record(row, parsed["totalPages"], query_label) for row in rows]
    except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
        return [build_error_record(query_label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail(tender_ids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(tender_ids)

    async def _one(i: int, tender_id: str):
        async with sem:
            client = EprocureClient(await proxy_url_fn())
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
        if mode not in ("list", "awarded", "detail"):
            raise input_error(f"mode must be 'list', 'awarded' or 'detail', got {mode!r}")

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

        if mode == "awarded":
            Actor.log.info("mode=awarded")
            records = await run_awarded(input_data, proxy_url_fn)
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
