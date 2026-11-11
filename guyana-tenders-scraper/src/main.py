import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import GuyanaEprocureClient
from src.extractor import (
    FrappeApiError,
    UnexpectedShape,
    build_error,
    build_record,
    normalize_detail,
    normalize_list_row,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

# NOTE: curl_cffi's own ConnectionError does not inherit from the builtin
# one (parallel MRO, same class name) -- both listed, portfolio-wide fix.
RETRYABLE_EXC = (RuntimeError, RequestException, ConnectionError, UnexpectedShape, FrappeApiError)


async def run_list_mode(fetch_detail: bool, max_items: int, max_concurrency: int, proxy_config) -> dict:
    """Fetches the complete current list of publicly advertised bid
    opportunities (no pagination exists upstream), optionally enriching each
    with its full-text project-advertisement detail. Returns
    `{"rows": [...]}` or `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = GuyanaEprocureClient(proxy_url)
    try:
        raw_rows = await client.fetch_bid_opportunities()
        rows = [normalize_list_row(r) for r in raw_rows][:max_items]

        if fetch_detail and rows:
            sem = asyncio.Semaphore(max_concurrency)

            async def _attach_detail(row: dict):
                project_id = row.get("project_id")
                if not project_id:
                    row["_detail"] = None
                    return
                async with sem:
                    try:
                        raw_detail = await client.fetch_project_advertisement(project_id)
                        row["_detail"] = normalize_detail(raw_detail)
                    except RETRYABLE_EXC as e:
                        row["_detail"] = None
                        row["_detailError"] = repr(e)

            await asyncio.gather(*(_attach_detail(row) for row in rows))

        return {"rows": rows}
    except RETRYABLE_EXC as e:
        log.warning(f"run_list_mode failed: {e!r}")
        return {"error": build_error("blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def run_detail_mode(project_id: str, proxy_config) -> dict:
    """Fetches a single project's full-text advertisement by id, independent
    of whether it still appears in the current list (e.g. a `project_id`
    shared from elsewhere). Returns `{"row": {...}}` or `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = GuyanaEprocureClient(proxy_url)
    try:
        raw_detail = await client.fetch_project_advertisement(project_id)
        return {"row": normalize_detail(raw_detail)}
    except FrappeApiError as e:
        log.warning(f"run_detail_mode({project_id!r}) -- not found/unpublished: {e!r}")
        return {"error": build_error("not_found", repr(e))}
    except RETRYABLE_EXC as e:
        log.warning(f"run_detail_mode({project_id!r}) failed: {e!r}")
        return {"error": build_error("blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode") or "list"
        if mode not in ("list", "detail"):
            raise input_error(f"'mode' must be 'list' or 'detail', got {mode!r}")

        max_items = min(int(input_data.get("maxItems", 100)), 5000)
        fetch_detail = bool(input_data.get("fetchDetail", False))
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        project_id = (input_data.get("projectId") or "").strip()

        if mode == "detail" and not project_id:
            raise input_error("'projectId' is required when mode='detail'")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "detail":
            Actor.log.info(f"mode=detail, projectId={project_id}")
            outcome = await run_detail_mode(project_id, proxy_config)
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
                return
            await Actor.push_data(build_record("S1-json-api-detail", outcome["row"]))
            return

        Actor.log.info(f"mode=list, maxItems={max_items}, fetchDetail={fetch_detail}, maxConcurrency={max_concurrency}")
        outcome = await run_list_mode(fetch_detail, max_items, max_concurrency, proxy_config)

        if "error" in outcome:
            await Actor.push_data(outcome["error"])
            return

        rows = outcome["rows"]
        Actor.log.info(f"Fetched {len(rows)} currently advertised bid opportunities")
        if not rows:
            # Genuinely empty is a valid, expected state for this platform
            # (a "what's open right now" board can legitimately have zero
            # entries between advertisement waves) -- not a hard error, but
            # still surfaced explicitly so a consumer can tell "ran fine,
            # nothing open" from "the actor is broken".
            await Actor.push_data(build_error("not_found", "0 currently advertised bid opportunities"))
            return

        source = "S1-json-api-detail" if fetch_detail else "S1-json-api"
        for row in rows:
            await Actor.push_data(build_record(source, row))
