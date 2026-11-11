"""Traveloka Hotel & Accommodation Scraper -- actor entry point."""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from apify import Actor

from src.client import GateError, TravelokaClient, TravelokaError
from src.constants import MAX_CALENDAR_MONTHS
from src.hotels import months_from, scrape_hotel
from src.resolver import hotel_id_from_url, resolve_query, sweep_sitemap

logger = logging.getLogger(__name__)


def _stay_spec(check_in: dt.date, nights: int, adults: int, rooms: int,
               currency: str) -> dict:
    def parts(day: dt.date) -> dict:
        return {"year": str(day.year), "month": str(day.month), "day": str(day.day)}

    return {
        "checkInDate": parts(check_in),
        "checkOutDate": parts(check_in + dt.timedelta(days=nights)),
        "numOfNights": nights,
        "numAdults": adults,
        "numChildren": 0,
        "childAges": [],
        "numInfants": 0,
        "numRooms": rooms,
        "currency": currency,
    }


def _parse_date(value: str | None, fallback_offset: int) -> dt.date:
    if value:
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            logger.warning("checkInDate %r is not YYYY-MM-DD; using default.", value)
    return dt.date.today() + dt.timedelta(days=fallback_offset)


async def _collect_targets(actor_input: dict, client) -> list[dict]:
    """Build the ordered, de-duplicated list of properties to scrape."""
    targets: list[dict] = []
    seen: set[str] = set()

    def add(hotel_id: str | None, source: str, name: str | None = None) -> None:
        if hotel_id and hotel_id not in seen:
            seen.add(hotel_id)
            targets.append({"hotelId": hotel_id, "source": source, "name": name})

    for raw in actor_input.get("hotelUrls") or []:
        url = raw.get("url") if isinstance(raw, dict) else raw
        resolved = hotel_id_from_url(str(url or ""))
        if resolved:
            add(resolved, "input:url")
        else:
            logger.warning("Could not read a property ID out of %r; skipping.", url)

    for raw in actor_input.get("hotelIds") or []:
        add(hotel_id_from_url(str(raw)), "input:id")

    per_query = int(actor_input.get("maxPropertiesPerQuery") or 10)
    for query in actor_input.get("searchQueries") or []:
        query = str(query or "").strip()
        if not query:
            continue
        try:
            hotels, _ = await resolve_query(client, query, per_query,
                                            client.locale, client.currency)
        except TravelokaError as exc:
            logger.warning("Autocomplete failed for %r: %s", query, exc)
            continue
        if not hotels:
            logger.warning("No property matched %r. Autocomplete matches property "
                           "names, not cities -- try the hotel's own name.", query)
        for row in hotels:
            add(str(row.get("id")), f"search:{query}", row.get("name"))

    sitemap_limit = int(actor_input.get("sitemapSweepLimit") or 0)
    if sitemap_limit > 0:
        try:
            for hotel_id, _slug in sweep_sitemap(
                    sitemap_limit, client.tls_profile, client.proxy_url,
                    int(actor_input.get("sitemapSkipLeaves") or 0)):
                add(hotel_id, "sitemap")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sitemap sweep failed: %s", exc)

    return targets


async def _proxy_pool(actor_input: dict, size: int = 12):
    """Pre-mint several proxy sessions so the client can rotate exit IPs.

    `new_url()` is async but the client bootstraps synchronously, so the URLs are
    generated up front and handed out by a plain callable.
    """
    proxy_config = actor_input.get("proxyConfiguration")
    if not proxy_config:
        return None, None
    configuration = await Actor.create_proxy_configuration(
        actor_proxy_input=proxy_config)
    if configuration is None:
        return None, None
    urls = [await configuration.new_url(uuid.uuid4().hex[:10]) for _ in range(size)]
    # AWS WAF captchas the session bootstrap on most of Apify's small datacenter
    # pool (3/12 sessions passed on 2026-10-15, the same ~5 IPs over and over)
    # while residential passed 11/11. When the chosen proxy is not residential,
    # queue residential sessions behind a few of the user's own so a run is not
    # lost to a captcha-only pool.
    groups = proxy_config.get("apifyProxyGroups") or []
    if proxy_config.get("useApifyProxy") and "RESIDENTIAL" not in groups:
        try:
            fallback = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
            if fallback is not None:
                urls = urls[:4] + [await fallback.new_url(uuid.uuid4().hex[:10])
                                   for _ in range(size - 4)]
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Residential fallback proxy unavailable: %s", exc)
    pool = list(urls)

    def next_url():
        if not pool:
            pool.extend(urls)
        return pool.pop(0)

    return urls[0], next_url


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        locale = actor_input.get("locale") or "en-id"
        currency = actor_input.get("currency") or "IDR"
        adults = int(actor_input.get("adults") or 2)
        rooms = int(actor_input.get("rooms") or 1)
        nights = int(actor_input.get("nights") or 1)
        check_in = _parse_date(actor_input.get("checkInDate"), 30)
        months_count = max(1, min(int(actor_input.get("calendarMonths") or 1),
                                  MAX_CALENDAR_MONTHS))
        max_properties = int(actor_input.get("maxProperties") or 50)

        proxy_url, proxy_factory = await _proxy_pool(actor_input)

        client = TravelokaClient(
            proxy_url=proxy_url, proxy_factory=proxy_factory,
            locale=locale, currency=currency,
            request_delay=float(actor_input.get("requestDelaySeconds") or 0.4),
        )
        try:
            client.bootstrap()
        except TravelokaError as exc:
            await Actor.push_data({
                "recordType": "ERROR",
                "error": f"Could not open a Traveloka session: {exc}",
                "scrapedAt": dt.datetime.now(dt.timezone.utc)
                .isoformat(timespec="seconds"),
            })
            await Actor.fail(status_message="Traveloka session bootstrap failed.")
            return

        targets = await _collect_targets(actor_input, client)
        if not targets:
            await Actor.push_data({
                "recordType": "ERROR",
                "error": "No properties to scrape. Supply hotelUrls, hotelIds, "
                         "searchQueries, or set sitemapSweepLimit above zero.",
                "scrapedAt": dt.datetime.now(dt.timezone.utc)
                .isoformat(timespec="seconds"),
            })
            await Actor.fail(status_message="No property targets resolved.")
            return

        targets = targets[:max_properties]
        options = {
            "stay": _stay_spec(check_in, nights, adults, rooms, currency),
            "months": months_from(check_in, months_count),
            "adults": adults,
            "rooms": rooms,
            "includeRooms": bool(actor_input.get("includeRooms", True)),
            "includeCalendar": bool(actor_input.get("includePriceCalendar", True)),
            "includeReviewSummary": bool(actor_input.get("includeReviewSummary", True)),
        }

        logger.info("Scraping %d properties (%d calendar month(s) each).",
                    len(targets), months_count)

        succeeded = gated = failed = 0
        for index, target in enumerate(targets, start=1):
            try:
                record = await scrape_hotel(client, target["hotelId"], options)
            except GateError as exc:
                record = {"hotelId": target["hotelId"], "recordType": "GATED",
                          "error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unhandled failure on %s", target["hotelId"])
                record = {"hotelId": target["hotelId"], "recordType": "ERROR",
                          "error": str(exc)[:400]}

            record.setdefault("scrapedAt", dt.datetime.now(dt.timezone.utc)
                              .isoformat(timespec="seconds"))
            record["inputSource"] = target["source"]
            record.setdefault("warnings", [])

            kind = record.get("recordType")
            if kind == "PROPERTY":
                succeeded += 1
            elif kind == "GATED":
                gated += 1
            else:
                failed += 1

            await Actor.push_data(record)
            if index % 10 == 0 or index == len(targets):
                logger.info("Progress: %d/%d (%d ok, %d gated, %d failed).",
                            index, len(targets), succeeded, gated, failed)

        await Actor.set_status_message(
            f"Scraped {succeeded} properties ({failed} failed, {gated} gated).")
