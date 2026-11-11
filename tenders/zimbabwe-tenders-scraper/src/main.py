import asyncio
import logging
import re

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import PrazClient
from src.constants import (
    AWARD_DETAIL_URL,
    AWARD_NOTICES_PAGE_URL,
    AWARD_NOTICES_URL,
    FORMER_TENDERS_PAGE_URL,
    FORMER_TENDERS_URL,
    LIVE_TENDERS_PAGE_URL,
    LIVE_TENDERS_URL,
    MAX_PAGES_HARD_CAP,
    TENDER_DETAIL_URL,
)
from src.extractor import (
    AWARD_DETAIL_ID_RE,
    TENDER_DETAIL_ID_RE,
    UnexpectedShape,
    build_detail_record,
    build_error,
    build_list_record,
    parse_award_notices,
    parse_detail_page,
    parse_former_tenders,
    parse_live_tenders,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _extract_id(value: str, url_re: re.Pattern) -> str | None:
    value = value.strip()
    if value.isdigit():
        return value
    m = url_re.search(value)
    return m.group(1) if m else None


async def _fetch_listing(
    client: PrazClient,
    first_url: str,
    page_url_tpl: str,
    parse_fn,
    max_items: int,
) -> list[dict]:
    """Walks a CakePHP paginator listing page by page until max_items is
    reached, a page returns no new rows, the hard page cap is hit, or a page
    turns out to be byte-identical (by first-row id) to the previous one --
    the last case is a generic guard against the confirmed Award Notices
    quirk where ?page=N is silently ignored server-side (see
    CRAWLING_METHOD.md), without hardcoding that quirk into this function."""
    r = await client.get(first_url)
    if r.status_code != 200:
        raise RuntimeError(f"http_{r.status_code}")
    rows, pagination = parse_fn(r.text)

    all_rows = list(rows)
    prev_first_id = rows[0].get("_id") if rows else None
    total_pages = pagination["totalPages"] if pagination else 1

    page = 2
    while len(all_rows) < max_items and page <= min(total_pages, MAX_PAGES_HARD_CAP):
        page_url = page_url_tpl.format(page=page)
        r = await client.get(page_url)
        if r.status_code != 200:
            log.warning(f"listing page {page} returned http_{r.status_code}, stopping pagination")
            break
        try:
            rows, _ = parse_fn(r.text)
        except UnexpectedShape as e:
            log.warning(f"listing page {page} unexpected shape, stopping pagination: {e}")
            break
        if not rows:
            break
        first_id = rows[0].get("_id")
        if first_id is not None and first_id == prev_first_id:
            log.warning(
                f"listing page {page} returned identical rows to the previous page "
                "(server-side pagination appears to be a no-op for this listing) -- stopping"
            )
            break
        prev_first_id = first_id
        all_rows.extend(rows)
        page += 1

    return all_rows[:max_items]


def _detail_id_key(detail_url_tpl: str) -> str:
    return "awardNoticeNumber" if detail_url_tpl == AWARD_DETAIL_URL else "tenderId"


async def _enrich_with_detail(
    client: PrazClient,
    rows: list[dict],
    detail_url_tpl: str,
    max_concurrency: int,
) -> None:
    """Mutates `rows` in place, adding a 'detail' or 'detailError' key per
    row that carries an '_id'."""
    sem = asyncio.Semaphore(max_concurrency)
    id_key = _detail_id_key(detail_url_tpl)

    async def _one(row: dict):
        row_id = row.get("_id")
        if not row_id:
            row["detailError"] = "no_id"
            return
        async with sem:
            try:
                r = await client.get(detail_url_tpl.format(tender_id=row_id, award_id=row_id))
                if r.status_code != 200:
                    row["detailError"] = f"http_{r.status_code}"
                    return
                detail = parse_detail_page(r.text)
                if id_key not in detail.get("fields", {}):
                    # The site returns HTTP 200 with a near-empty template
                    # for a nonexistent id (confirmed live) rather than a
                    # 404 -- detect that case via the missing id field
                    # instead of surfacing a confusingly-blank "success".
                    row["detailError"] = "not_found"
                    return
                row["detail"] = detail
            except UnexpectedShape as e:
                row["detailError"] = f"unexpected_shape:{e}"
            except (RuntimeError, ConnectionError, RequestException) as e:
                row["detailError"] = f"blocked_or_transient:{e!r}"

    await asyncio.gather(*(_one(row) for row in rows))


async def run_live(proxy_config, max_items: int, fetch_details: bool, max_concurrency: int) -> list[dict]:
    query = "latest"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = PrazClient(proxy_url=proxy_url)
    try:
        rows = await _fetch_listing(client, LIVE_TENDERS_URL, LIVE_TENDERS_PAGE_URL, parse_live_tenders, max_items)
        if fetch_details:
            await _enrich_with_detail(client, rows, TENDER_DETAIL_URL, max_concurrency)
        return [build_list_record(query, "S1-live-tenders-html", row) for row in rows]
    except UnexpectedShape as e:
        return [build_error(query, "unexpected_shape", str(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_former(proxy_config, max_items: int, fetch_details: bool, max_concurrency: int) -> list[dict]:
    query = "former"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = PrazClient(proxy_url=proxy_url)
    try:
        rows = await _fetch_listing(
            client, FORMER_TENDERS_URL, FORMER_TENDERS_PAGE_URL, parse_former_tenders, max_items
        )
        if fetch_details:
            await _enrich_with_detail(client, rows, TENDER_DETAIL_URL, max_concurrency)
        return [build_list_record(query, "S1-former-tenders-html", row) for row in rows]
    except UnexpectedShape as e:
        return [build_error(query, "unexpected_shape", str(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_awards(proxy_config, max_items: int, fetch_details: bool, max_concurrency: int) -> list[dict]:
    query = "awards"
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = PrazClient(proxy_url=proxy_url)
    try:
        rows = await _fetch_listing(
            client, AWARD_NOTICES_URL, AWARD_NOTICES_PAGE_URL, parse_award_notices, max_items
        )
        if fetch_details:
            await _enrich_with_detail(client, rows, AWARD_DETAIL_URL, max_concurrency)
        return [build_list_record(query, "S1-award-notices-html", row) for row in rows]
    except UnexpectedShape as e:
        return [build_error(query, "unexpected_shape", str(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [build_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_detail_one(target: str, kind: str, proxy_url: str | None) -> dict:
    """kind is 'tender' or 'award'."""
    if kind == "award":
        record_id = _extract_id(target, AWARD_DETAIL_ID_RE)
        url_tpl, id_field, source = AWARD_DETAIL_URL, "awardNoticeNumber", "S1-award-detail-html"
    else:
        record_id = _extract_id(target, TENDER_DETAIL_ID_RE)
        url_tpl, id_field, source = TENDER_DETAIL_URL, "tenderId", "S1-tender-detail-html"

    if not record_id:
        return build_error(target, "invalid_input", f"Could not extract a numeric id from {target!r}")

    client = PrazClient(proxy_url=proxy_url)
    try:
        url = url_tpl.format(tender_id=record_id, award_id=record_id)
        r = await client.get(url)
        if r.status_code != 200:
            return build_error(target, f"http_{r.status_code}")
        detail = parse_detail_page(r.text)
        if _detail_id_key(url_tpl) not in detail.get("fields", {}):
            # See _enrich_with_detail: nonexistent ids return HTTP 200 with
            # a near-empty template rather than a 404.
            return build_error(target, "not_found", f"No record found for id {record_id!r}")
        return build_detail_record(target, source, id_field, record_id, detail)
    except UnexpectedShape as e:
        return build_error(target, "unexpected_shape", str(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return build_error(target, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = (input_data.get("mode") or "latest").strip().lower()
        max_items = int(input_data.get("maxItems", 20))
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "latest":
            Actor.log.info(f"mode=latest max_items={max_items} fetch_details={fetch_details}")
            records = await run_live(proxy_config, max_items, fetch_details, max_concurrency)
            await Actor.push_data(records)

        elif mode == "former":
            Actor.log.info(f"mode=former max_items={max_items} fetch_details={fetch_details}")
            records = await run_former(proxy_config, max_items, fetch_details, max_concurrency)
            await Actor.push_data(records)

        elif mode == "awards":
            Actor.log.info(f"mode=awards max_items={max_items} fetch_details={fetch_details}")
            records = await run_awards(proxy_config, max_items, fetch_details, max_concurrency)
            await Actor.push_data(records)

        elif mode == "detail":
            tender_targets = [str(x).strip() for x in (input_data.get("tenderIds") or []) if str(x).strip()]
            award_targets = [str(x).strip() for x in (input_data.get("awardIds") or []) if str(x).strip()]
            if not tender_targets and not award_targets:
                raise input_error("Mode 'detail' requires 'tenderIds' and/or 'awardIds'.")

            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded(target: str, kind: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_detail_one(target, kind, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(
                f"mode=detail tenderTargets={len(tender_targets)} awardTargets={len(award_targets)} "
                f"maxConcurrency={max_concurrency}"
            )
            await asyncio.gather(
                *(_bounded(t, "tender") for t in tender_targets),
                *(_bounded(t, "award") for t in award_targets),
            )

        else:
            raise input_error(f"Unknown mode {mode!r} -- expected 'latest', 'former', 'awards', or 'detail'.")
