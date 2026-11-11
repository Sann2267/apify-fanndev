"""Mode dispatch for the Google Hotels rate-comparison Actor.

Five modes over two requests-worth of surface:

* ``search``    -- 1 request per query, up to 21 hotel cards.
* ``hotel``     -- 1 request per hotel: detail + nested cross-OTA rates.
* ``rates``     -- the same request, flattened to one record per OTA quote.
* ``sponsored`` -- the paid placements from the same page, kept apart from rates.
* ``reference`` -- probes the source and reports measurable evidence, including
  which TLS profile won. This is the mode that detects a platform-side IP gate
  in seconds instead of halfway through a paid run.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import BlockedUpstream, EntityNotFound, GoogleHotelsClient
from src.constants import CARDS_PER_QUERY, MODES, URL_ENTITY, URL_SEARCH
from src.extractor import (
    HollowEntityPage,
    extract_error,
    parse_entity,
    parse_rates,
    parse_search,
    parse_sponsored,
    wrap_reference,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, RuntimeError, ConnectionError)

RECORD_TYPES = {
    "travel-search-ssr": "HOTEL",
    "travel-entity-prices-ssr": "HOTEL",
    "reference": "SURFACE",
    "error": "ERROR",
}


RECORD_TYPE_BY_MODE = {"rates": "RATE", "sponsored": "SPONSORED", "hotel": "HOTEL"}


def envelope(record: dict, input_value: str, record_type: str | None = None) -> dict:
    """Add the portfolio's mandatory meta fields (.ai/conventions/dataset-envelope.md).

    Applied at the push boundary so the parsers stay pure functions of HTML and
    can be unit-tested without an Actor context.
    """
    record.setdefault("_input", input_value)
    record.setdefault("_source", "none")
    record["_scrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # The record's own source wins over the caller's mode hint: a failure row
    # inside mode 'rates' is an ERROR, not a RATE, and mislabelling it would
    # hide failures from anyone filtering the dataset by recordType.
    by_source = RECORD_TYPES.get(record["_source"])
    record.setdefault(
        "recordType",
        by_source if by_source in ("SURFACE", "ERROR") else (record_type or by_source or "HOTEL"),
    )
    return record


def normalize_entity_id(raw: str) -> str:
    """Accepts a bare entity id or any Google Hotels URL containing one.

    Google's ids are opaque base64-ish strings (``ChcIyo2FjenOuZ8x...``), so
    anything that is not extracted from a URL is passed through as-is and the
    request itself decides whether it exists.
    """
    value = (raw or "").strip()
    m = re.search(r"/entity/([A-Za-z0-9_\-]+)", value)
    if m:
        return m.group(1)
    if value.startswith("http"):
        return ""
    return value


async def run_search(
    queries: list[str],
    hl: str,
    gl: str,
    max_items: int,
    fetch_rates: bool,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    """One request per query. Optionally enrich each hotel with its rate table.

    ``fetch_rates`` is off by default because it costs one extra request per
    hotel -- 21x the requests of a bare search -- and the caller should opt
    into that deliberately.
    """
    pushed = 0
    for query in queries:
        if pushed >= max_items:
            break
        client = GoogleHotelsClient(proxy_url=await proxy_url_factory())
        try:
            url = URL_SEARCH.format(query=query.replace(" ", "+"), hl=hl, gl=gl)
            html, profile = await client.get_html(url)
            records = parse_search(html, query)
            if not records:
                await push(
                    [
                        extract_error(
                            query,
                            "no_hotels_parsed",
                            f"200 of usable size but no hotel cards found (TLS {profile}) -- "
                            f"either the query matched no property or the card markup moved",
                        )
                    ],
                    query,
                )
                continue
            log.info(f"search {query!r}: {len(records)} hotel(s) via TLS {profile}")
        except (BlockedUpstream, *TRANSIENT) as exc:
            await push([extract_error(query, "blocked_or_transient", repr(exc))], query)
            continue
        finally:
            await client.close()

        if fetch_rates:
            records = await _enrich_with_rates(records, hl, gl, max_concurrency, proxy_url_factory)

        records = records[: max_items - pushed]
        await push(records, query)
        pushed += len(records)

    return pushed


async def _enrich_with_rates(
    records: list[dict], hl: str, gl: str, max_concurrency: int, proxy_url_factory
) -> list[dict]:
    """Attach each hotel's rate table, keeping the card if the entity page
    fails -- a partial record beats a dropped one."""
    sem = asyncio.Semaphore(max_concurrency)

    async def one(record: dict) -> dict:
        async with sem:
            client = GoogleHotelsClient(proxy_url=await proxy_url_factory())
            try:
                url = URL_ENTITY.format(entity_id=record["entityId"], hl=hl, gl=gl)
                html, _ = await client.get_html(url)
                detail = parse_entity(record["entityId"], html)
                merged = {**record, **{k: v for k, v in detail.items() if v is not None}}
                merged["searchQuery"] = record.get("searchQuery")
                return merged
            except (EntityNotFound, HollowEntityPage, ValueError, *TRANSIENT) as exc:
                record["_rateError"] = repr(exc)
                return record
            finally:
                await client.close()

    return list(await asyncio.gather(*(one(r) for r in records)))


async def run_entities(
    identifiers: list[str],
    hl: str,
    gl: str,
    mode: str,
    max_items: int,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    """Fetch entity pages and emit them per ``mode``: nested, flat or sponsored."""
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        entity_id = normalize_entity_id(raw)
        if not entity_id:
            await push(
                [
                    extract_error(
                        raw,
                        "invalid_entity_id",
                        "expected a Google Hotels entity id or a /travel/hotels/entity/<id> URL",
                    )
                ],
                raw,
            )
            return

        async with sem:
            client = GoogleHotelsClient(proxy_url=await proxy_url_factory())
            try:
                url = URL_ENTITY.format(entity_id=entity_id, hl=hl, gl=gl)
                html, _ = await client.get_html(url)
                # rates/sponsored parse fragments rather than the header, so
                # they cannot notice Google's 200-with-error-page on their own;
                # parse_entity is what detects it, hence this guard first.
                if mode in ("rates", "sponsored"):
                    parse_entity(entity_id, html)

                if mode == "rates":
                    records = parse_rates(entity_id, html)
                    if not records:
                        records = [
                            extract_error(
                                entity_id,
                                "no_rates_published",
                                "the hotel page carries no OTA quote right now -- normal for "
                                "small properties and for sold-out dates",
                            )
                        ]
                elif mode == "sponsored":
                    records = parse_sponsored(entity_id, html)
                    if not records:
                        records = [
                            extract_error(
                                entity_id, "no_sponsored_placements", "no paid placement on this page"
                            )
                        ]
                else:
                    records = [parse_entity(entity_id, html)]
            except (EntityNotFound, HollowEntityPage) as exc:
                records = [extract_error(entity_id, "not_found", str(exc) or "no hotel under this entity id")]
            except ValueError as exc:
                records = [extract_error(entity_id, "shape_changed", str(exc))]
            except TRANSIENT as exc:
                records = [extract_error(entity_id, "blocked_or_transient", repr(exc))]
            finally:
                await client.close()

            async with lock:
                if pushed >= max_items:
                    return
                room = max_items - pushed
                records = records[:room]
                pushed += len(records)
            await push(records, raw, RECORD_TYPE_BY_MODE.get(mode))

    await asyncio.gather(*(one(i) for i in identifiers))
    return pushed


async def run_reference(hl: str, gl: str, proxy_url: str | None) -> list[dict]:
    """Probe both surfaces and report measurable evidence.

    Deliberately reports the currency Google *returned* rather than one the
    caller asked for, because the currency is not selectable on this surface.
    """
    client = GoogleHotelsClient(proxy_url=proxy_url)
    url = URL_SEARCH.format(query="hotels+in+singapore", hl=hl, gl=gl)
    try:
        html, profile = await client.get_html(url)
        hotels = parse_search(html, "hotels in singapore")
        sample = {
            "searchCards": len(hotels),
            "expectedCardsPerQuery": CARDS_PER_QUERY,
            "returnedCurrency": next((h["currency"] for h in hotels if h.get("currency")), None),
            "stayWindowGoogleChose": next((h["stayWindow"] for h in hotels if h.get("stayWindow")), None),
            "sampleHotel": hotels[0]["name"] if hotels else None,
            "sampleEntityId": hotels[0]["entityId"] if hotels else None,
        }

        if hotels:
            entity_url = URL_ENTITY.format(entity_id=hotels[0]["entityId"], hl=hl, gl=gl)
            entity_html, _ = await client.get_html(entity_url)
            detail = parse_entity(hotels[0]["entityId"], entity_html)
            sample["rateRowsOnFirstHotel"] = detail["rateCount"]
            sample["providersOnFirstHotel"] = [
                r["provider"] for r in detail["rates"][:8] if r.get("provider")
            ]
            sample["rateSpread"] = detail["rateSpread"]
            sample["sponsoredPlacements"] = len(parse_sponsored(hotels[0]["entityId"], entity_html))

        return [
            wrap_reference(
                url,
                bool(hotels),
                "payload parsed" if hotels else "200 but no cards parsed",
                sample,
                profile,
            )
        ]
    except Exception as exc:  # noqa: BLE001 -- a probe reports, it never raises
        return [wrap_reference(url, False, repr(exc))]
    finally:
        await client.close()


def _clean_list(input_data: dict, single_key: str, list_key: str) -> list[str]:
    values = list(input_data.get(list_key) or [])
    if input_data.get(single_key):
        values.insert(0, input_data[single_key])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "search")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        hl = str(input_data.get("languageCode") or "en")
        gl = str(input_data.get("countryCode") or "us")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict], input_value: str, record_type: str | None = None):
            if records:
                await Actor.push_data(
                    [envelope(r, input_value, record_type) for r in records]
                )

        if mode == "reference":
            records = await run_reference(hl, gl, await new_proxy_url())
            Actor.log.info(
                f"mode=reference: available={records[0].get('isAvailable')} "
                f"tls={records[0].get('winningTlsProfile')} {records[0].get('sample')}"
            )
            await push(records, "reference")
            return

        if mode == "search":
            queries = _clean_list(input_data, "searchQuery", "searchQueries")
            if not queries:
                raise input_error(
                    "Provide 'searchQuery' or 'searchQueries' for mode 'search', "
                    "e.g. 'hotels in Singapore'."
                )
            count = await run_search(
                queries,
                hl,
                gl,
                max_items,
                bool(input_data.get("fetchRates", False)),
                max_concurrency,
                new_proxy_url,
                push,
            )
            Actor.log.info(f"mode=search queries={len(queries)} -> {count} record(s)")
            return

        identifiers = _clean_list(input_data, "hotelId", "hotelIds")
        if not identifiers:
            raise input_error(
                f"Provide 'hotelId' or 'hotelIds' for mode {mode!r} -- a Google Hotels "
                f"entity id, or the /travel/hotels/entity/<id> URL it came from. "
                f"Run mode 'search' first to collect them."
            )
        pushed = await run_entities(
            identifiers, hl, gl, mode, max_items, max_concurrency, new_proxy_url, push
        )
        Actor.log.info(f"mode={mode} hotels={len(identifiers)} -> {pushed} record(s)")
