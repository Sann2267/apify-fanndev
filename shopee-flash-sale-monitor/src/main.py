"""Mode dispatch for the Shopee flash-sale monitor.

* ``monitor``   -- sessions plus every item in the sessions you asked for.
  This is the price-tracking mode: run it on a schedule and diff on ``itemId``.
* ``sessions``  -- the session calendar only. One request per country, useful
  for deciding *when* to run the expensive mode.
* ``reference`` -- probe the surface per country and report what answered.

A gated endpoint produces a ``GATED`` record naming the endpoint, never an empty
result set. On this source that distinction is the whole game: most of Shopee's
API answers 403 from a plain client, and a scraper that swallows it looks
identical to one reporting "no flash sales today".
"""

import asyncio
import logging
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, Gated, NotFound, ShopeeClient
from src.constants import DOMAINS, MODES, URL_ITEMS, URL_SESSIONS
from src.extractor import parse_items, parse_sessions
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _envelope(payload: dict, *, source: str, query: str, record_type: str,
              country: str | None = None, attempts: int | None = None) -> dict:
    return {
        "_input": query,
        "_query": query,
        "_source": source,
        "_country": country,
        "_scrapedAt": _now(),
        "_attempts": attempts,
        "recordType": record_type,
        **payload,
    }


async def _sessions_for(client: ShopeeClient, country: str):
    domain = DOMAINS[country]
    payload, profile, attempts = await client.get_json(
        URL_SESSIONS.format(domain=domain), domain, country)
    return parse_sessions(payload), profile, attempts


async def _items_for(client: ShopeeClient, country: str, promotion_id, limit: int):
    domain = DOMAINS[country]
    url = URL_ITEMS.format(domain=domain, limit=limit, offset=0, promotionid=promotion_id or 0)
    payload, profile, attempts = await client.get_json(url, domain, country)
    items = parse_items(payload, country)
    for item in items:
        item["url"] = (f"https://{domain}/product-i.{item['shopId']}.{item['itemId']}"
                       if item.get("shopId") and item.get("itemId") else None)
    return items, profile, attempts


async def _run_sessions(client, countries, concurrency) -> int:
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(country: str) -> list[dict]:
        async with semaphore:
            try:
                sessions, profile, attempts = await _sessions_for(client, country)
            except Gated as exc:
                return [_envelope({"error": "gated", "message": str(exc),
                                   "hint": "Shopee refused this endpoint at its load balancer. "
                                           "Retry through a residential proxy."},
                                  source="flash-sale-sessions", query=country,
                                  record_type="GATED", country=country)]
            except (Blocked, NotFound) as exc:
                return [_envelope({"error": type(exc).__name__.lower(), "message": str(exc)},
                                  source="flash-sale-sessions", query=country,
                                  record_type="ERROR", country=country)]
            records = []
            for session in sessions:
                session["_tlsProfile"] = profile
                records.append(_envelope(session, source="flash-sale-sessions",
                                         query=country, record_type="SESSION",
                                         country=country, attempts=attempts))
            if not records:
                records.append(_envelope(
                    {"error": "no-sessions",
                     "hint": "The endpoint answered normally and listed no sessions."},
                    source="flash-sale-sessions", query=country,
                    record_type="EMPTY", country=country, attempts=attempts))
            return records

    pushed = 0
    for coro in asyncio.as_completed([worker(c) for c in countries]):
        for record in await coro:
            await Actor.push_data(record)
            pushed += 1
    return pushed


async def _run_monitor(client, countries, limit, ongoing_only, concurrency) -> int:
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(country: str) -> list[dict]:
        async with semaphore:
            try:
                sessions, _, attempts = await _sessions_for(client, country)
            except Gated as exc:
                return [_envelope({"error": "gated", "message": str(exc)},
                                  source="flash-sale-sessions", query=country,
                                  record_type="GATED", country=country)]
            except (Blocked, NotFound) as exc:
                return [_envelope({"error": type(exc).__name__.lower(), "message": str(exc)},
                                  source="flash-sale-sessions", query=country,
                                  record_type="ERROR", country=country)]

            wanted = [s for s in sessions if s["isOngoing"]] if ongoing_only else sessions
            if ongoing_only and not wanted:
                return [_envelope(
                    {"error": "no-ongoing-session",
                     "sessionsAvailable": len(sessions),
                     "hint": "No flash sale is running in this country right now. "
                             "Turn off ongoingOnly to pull upcoming sessions too."},
                    source="flash-sale-sessions", query=country,
                    record_type="EMPTY", country=country, attempts=attempts)]

            records: list[dict] = []
            for session in wanted:
                try:
                    items, profile, item_attempts = await _items_for(
                        client, country, session["promotionId"], limit)
                except Gated as exc:
                    records.append(_envelope(
                        {"promotionId": session["promotionId"], "error": "gated",
                         "message": str(exc)},
                        source="flash-sale-items", query=country,
                        record_type="GATED", country=country))
                    continue
                except (Blocked, NotFound) as exc:
                    records.append(_envelope(
                        {"promotionId": session["promotionId"],
                         "error": type(exc).__name__.lower(), "message": str(exc)},
                        source="flash-sale-items", query=country,
                        record_type="ERROR", country=country))
                    continue

                log.info("%s session %s -> %d item(s)", country,
                         session["promotionId"], len(items))
                for position, item in enumerate(items, start=1):
                    item["promotionId"] = session["promotionId"]
                    item["sessionName"] = session["name"]
                    item["sessionIsOngoing"] = session["isOngoing"]
                    item["sessionStartTime"] = session["startTime"]
                    item["sessionEndTime"] = session["endTime"]
                    item["sessionPosition"] = position
                    item["_tlsProfile"] = profile
                    records.append(_envelope(item, source="flash-sale-items",
                                             query=country, record_type="ITEM",
                                             country=country, attempts=item_attempts))
            return records

    pushed = 0
    for coro in asyncio.as_completed([worker(c) for c in countries]):
        for record in await coro:
            await Actor.push_data(record)
            pushed += 1
    return pushed


async def _run_reference(client, countries) -> int:
    probes = []
    for country in countries:
        entry = {"country": country, "domain": DOMAINS[country]}
        try:
            sessions, profile, attempts = await _sessions_for(client, country)
            entry.update({"ok": True, "sessions": len(sessions), "attempts": attempts,
                          "tlsProfile": profile,
                          "ongoing": sum(1 for s in sessions if s["isOngoing"])})
            if sessions:
                items, _, _ = await _items_for(client, country,
                                               sessions[0]["promotionId"], 100)
                entry["itemsInFirstSession"] = len(items)
                entry["samplePrice"] = items[0]["price"] if items else None
        except Exception as exc:
            entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        probes.append(entry)

    await Actor.push_data(_envelope(
        {
            "surface": "shopee /api/v4/flash_sale/*",
            "probes": probes,
            "known": {
                "openEndpoints": ["flash_sale/get_all_sessions",
                                  "flash_sale/flash_sale_get_items"],
                "gatedEndpoints": ["search/search_items", "item/get_ratings",
                                   "shop/get_shop_seo"],
                "noPublicApi": ["product Q&A - every documented path returns 404"],
                "priceScaling": "Integers scaled by 100000; this Actor divides them.",
                "itemsPerSession": "16 at limit=16, 53 at limit=100 - the cap is the "
                                   "session size, not a page size.",
            },
        },
        source="reference", query="reference", record_type="SURFACE"))
    return 1


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        mode = (actor_input.get("mode") or "monitor").strip()
        if mode not in MODES:
            raise input_error(f"mode must be one of {MODES}, got {mode!r}")

        countries = [c.strip().upper() for c in (actor_input.get("countries") or ["ID"])]
        unknown = [c for c in countries if c not in DOMAINS]
        if unknown:
            raise input_error(f"unknown country code(s) {unknown}; "
                             f"supported: {sorted(DOMAINS)}")

        limit = max(1, min(int(actor_input.get("itemsPerSession") or 100), 200))
        concurrency = max(1, min(int(actor_input.get("concurrency") or 3), 8))
        ongoing_only = bool(actor_input.get("ongoingOnly", False))

        proxy_url = None
        proxy_config = actor_input.get("proxyConfiguration")
        if proxy_config:
            configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_config)
            if configuration:
                proxy_url = await configuration.new_url()

        client = ShopeeClient(proxy_url=proxy_url, profile=actor_input.get("tlsProfile"))

        if mode == "reference":
            pushed = await _run_reference(client, countries)
        elif mode == "sessions":
            pushed = await _run_sessions(client, countries, concurrency)
        else:
            pushed = await _run_monitor(client, countries, limit, ongoing_only, concurrency)

        log.info("pushed %d record(s) in mode=%s", pushed, mode)
