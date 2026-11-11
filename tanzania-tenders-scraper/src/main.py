import asyncio
from datetime import datetime, timedelta, timezone

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, RecordNotFound, fetch_record_detail, fetch_records_page
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP
from src.extractor import UnexpectedShape, build_detail_record, build_error_record, build_list_record
from src.input_errors import input_error

DEFAULT_SINCE_DAYS_BACK = 90


def _parse_iso(value: str) -> datetime:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_since() -> str:
    return _format_iso(datetime.now(timezone.utc) - timedelta(days=DEFAULT_SINCE_DAYS_BACK))


async def run_list(since: str | None, max_results: int, proxy_url_fn) -> list[dict]:
    """Pages through NeST's records feed for records dated on/after `since`.

    NeST's own `cursor` query parameter is accepted but not honoured
    server-side (every value returns the same fixed page) -- see
    client.py / CRAWLING_METHOD.md. Real pagination here advances `since`
    itself, past the latest record date seen in each 5-record page,
    de-duplicating by ocid across the date-boundary overlap this causes.
    """
    current_since = (since or "").strip() or _default_since()
    records: list[dict] = []
    seen_ocids: set[str] = set()
    pages_fetched = 0

    while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
        proxy_url = await proxy_url_fn()
        try:
            page = await fetch_records_page(current_since, proxy_url=proxy_url)
        except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:since={current_since}", "blocked_or_transient", repr(e)))
            break

        pages_fetched += 1
        items = page.get("records") if isinstance(page, dict) else None
        if not items:
            Actor.log.info(f"list: no more records at since={current_since!r} -- reached the end of the feed.")
            break

        dates: list[datetime] = []
        for item in items:
            cr = item.get("compiledRelease") if isinstance(item, dict) else None
            raw_date = (cr or {}).get("date")
            if raw_date:
                try:
                    dates.append(_parse_iso(raw_date))
                except ValueError:
                    continue
        if not dates:
            raise UnexpectedShape(
                f"list: none of the {len(items)} record(s) at since={current_since!r} had a parseable "
                "compiledRelease.date -- can't advance pagination; upstream shape has likely changed"
            )

        for item in items:
            ocid = item.get("ocid") if isinstance(item, dict) else None
            if not ocid or ocid in seen_ocids:
                continue
            seen_ocids.add(ocid)
            records.append(build_list_record(item, current_since))  # raises UnexpectedShape -- not swallowed
            if len(records) >= max_results:
                break

        next_since_dt = max(dates) + timedelta(seconds=1)
        next_since = _format_iso(next_since_dt)
        if _parse_iso(next_since) <= _parse_iso(current_since):
            Actor.log.info(
                f"list: pagination window stalled at since={current_since!r} (couldn't advance past it) -- "
                f"stopping with {len(records)} record(s) rather than looping forever."
            )
            break
        current_since = next_since

        if len(records) < max_results:
            await asyncio.sleep(LIST_PAGE_DELAY)

    if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
        Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")

    return records


async def run_detail(ocids: list[str], max_concurrency: int, proxy_url_fn) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[dict | None] = [None] * len(ocids)

    async def _one(i: int, ocid: str):
        async with sem:
            proxy_url = await proxy_url_fn()
            try:
                item = await fetch_record_detail(ocid, proxy_url=proxy_url)
            except RecordNotFound:
                results[i] = build_error_record(ocid, "not_found", "no record exists for this ocid")
                return
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, per the
                # portfolio-wide Babak 22b fix.
                results[i] = build_error_record(ocid, "blocked_or_transient", repr(e))
                return
            results[i] = build_detail_record(ocid, item)  # raises UnexpectedShape -- not swallowed

    await asyncio.gather(*(_one(i, ocid) for i, ocid in enumerate(ocids)))
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
            since = input_data.get("since")
            max_results = int(input_data.get("maxResults", 50))
            max_results = max(1, min(max_results, 5000))

            Actor.log.info(f"mode=list since={since!r} maxResults={max_results}")
            records = await run_list(since, max_results, proxy_url_fn)
            await Actor.push_data(records)
            return

        # mode == "detail"
        raw_ids = []
        if input_data.get("ocid"):
            raw_ids.append(input_data["ocid"])
        raw_ids.extend(input_data.get("ocids") or [])
        ocids = []
        seen = set()
        for raw in raw_ids:
            ocid = str(raw).strip()
            if ocid and ocid not in seen:
                seen.add(ocid)
                ocids.append(ocid)
        if not ocids:
            raise input_error("Provide 'ocid' or a non-empty 'ocids' array (NeST OCDS record identifiers).")

        max_concurrency = int(input_data.get("maxConcurrency", 3))
        max_concurrency = max(1, min(max_concurrency, 5))

        Actor.log.info(f"mode=detail {len(ocids)} ocid(s), maxConcurrency={max_concurrency}")
        records = await run_detail(ocids, max_concurrency, proxy_url_fn)
        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
