import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NotFound, SintaClient
from src.constants import (
    MODES,
    PARAM_QUERY,
    PATH_AFFILIATIONS,
    PATH_AUTHOR_PROFILE,
    PATH_AUTHORS,
)
from src.extractor import (
    absolute,
    extract_error,
    parse_affiliations,
    parse_author_profile,
    parse_authors,
    sinta_id_from_input,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


async def run_authors(query: str | None, max_items: int, proxy_url: str | None) -> list[dict]:
    label = f"authors:{query}" if query else "authors:*"
    params = {PARAM_QUERY: query} if query else {}
    client = SintaClient(proxy_url=proxy_url)
    try:
        rows, totals = await client.paginate(
            PATH_AUTHORS, params, max_items, parse_authors, "sintaId"
        )
        records = []
        for r in rows:
            rec = wrap(r, label, record_type="AUTHOR_CARD")
            rec["_totalRecordsAvailable"] = totals.get("totalRecords")
            records.append(rec)
        return records
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_affiliations(max_items: int, proxy_url: str | None) -> list[dict]:
    client = SintaClient(proxy_url=proxy_url)
    try:
        rows, totals = await client.paginate(
            PATH_AFFILIATIONS, {}, max_items, parse_affiliations, "affiliationId"
        )
        records = []
        for r in rows:
            rec = wrap(r, "affiliations", record_type="AFFILIATION")
            rec["_totalRecordsAvailable"] = totals.get("totalRecords")
            records.append(rec)
        return records
    except TRANSIENT as e:
        return [extract_error("affiliations", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_author(raw_input: str, proxy_url: str | None) -> dict:
    sinta_id = sinta_id_from_input(raw_input)
    if not sinta_id:
        return extract_error(raw_input, "invalid_sinta_id", "expected a numeric SINTA ID or a profile URL")
    path = PATH_AUTHOR_PROFILE.format(sinta_id=sinta_id)

    client = SintaClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(path)
        data = parse_author_profile(html, absolute(path))
        if not data.get("name"):
            return extract_error(raw_input, "not_a_profile", f"no researcher parsed from {path}")
        return wrap(data, raw_input, record_type="AUTHOR_PROFILE")
    except NotFound:
        return extract_error(raw_input, "not_found", path)
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "authors")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 100))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "affiliations":
            records = await run_affiliations(max_items, await new_proxy_url())
            Actor.log.info(f"mode=affiliations: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "authors":
            query = (input_data.get("query") or "").strip() or None
            records = await run_authors(query, max_items, await new_proxy_url())
            Actor.log.info(f"mode=authors query={query!r} -> {len(records)} record(s)")
            await Actor.push_data(records)

            if input_data.get("enrichProfiles"):
                ids = [r["sintaId"] for r in records if r.get("sintaId")]
                Actor.log.info(f"enrichProfiles: fetching {len(ids)} profile(s)")
                await _fetch_authors(ids, int(input_data.get("maxConcurrency", 4)), new_proxy_url)
            return

        # mode == "author"
        ids = list(input_data.get("sintaIds") or [])
        if input_data.get("sintaId"):
            ids.insert(0, input_data["sintaId"])
        if not ids:
            raise input_error("Provide 'sintaId' or 'sintaIds' when mode is 'author'.")
        seen = set()
        ids = [str(i) for i in ids if not (i in seen or seen.add(i))]

        Actor.log.info(f"mode=author: {len(ids)} profile(s)")
        await _fetch_authors(ids, int(input_data.get("maxConcurrency", 4)), new_proxy_url)


async def _fetch_authors(ids: list[str], max_concurrency: int, new_proxy_url) -> None:
    sem = asyncio.Semaphore(max_concurrency)

    async def _bounded(i: str):
        async with sem:
            record = await run_author(i, await new_proxy_url())
            await Actor.push_data(record)

    await asyncio.gather(*(_bounded(i) for i in ids))
