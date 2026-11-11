"""Traveloka Ground Transport (Bus & Shuttle) Monitor -- actor entry point."""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from apify import Actor

from src.client import GateError, TravelokaClient, TravelokaError
from src.constants import DEFAULT_MAX_DEPARTURES, HARD_MAX_DEPARTURES
from src.transport import resolve_location, search_departures, summarise_route

logger = logging.getLogger(__name__)

SEPARATORS = ("->", "-->", " to ", " - ", ">", "-")


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


def _split_route(text: str) -> tuple[str, str] | None:
    text = (text or "").strip()
    if not text:
        return None
    for separator in SEPARATORS:
        if separator in text:
            origin, _, destination = text.partition(separator)
            if origin.strip() and destination.strip():
                return origin.strip(), destination.strip()
    return None


def _route_pairs(actor_input: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in actor_input.get("routes") or []:
        text = raw.get("route") if isinstance(raw, dict) else str(raw or "")
        pair = _split_route(str(text))
        if pair:
            pairs.append(pair)
        else:
            logger.warning("Route %r has no separator (use 'Jakarta-Bandung'); "
                           "skipping.", text)
    origin = (actor_input.get("origin") or "").strip()
    destination = (actor_input.get("destination") or "").strip()
    if origin and destination:
        pairs.append((origin, destination))
    return pairs


def _dates(actor_input: dict) -> list[dt.date]:
    start_raw = actor_input.get("departureDate")
    start = dt.date.today() + dt.timedelta(days=7)
    if start_raw:
        try:
            start = dt.date.fromisoformat(str(start_raw))
        except ValueError:
            logger.warning("departureDate %r is not YYYY-MM-DD; using default.",
                           start_raw)
    span = max(1, min(int(actor_input.get("daysToMonitor") or 1), 30))
    return [start + dt.timedelta(days=offset) for offset in range(span)]


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        adults = int(actor_input.get("adults") or 1)
        max_departures = max(1, min(
            int(actor_input.get("maxDeparturesPerSearch") or DEFAULT_MAX_DEPARTURES),
            HARD_MAX_DEPARTURES))
        dedupe = (actor_input.get("dedupeBy") or "trip").lower()
        product_types = list(actor_input.get("productTypes") or [])
        want_departures = bool(actor_input.get("includeDepartures", True))
        want_summary = bool(actor_input.get("includeRouteSummary", True))

        proxy_url, proxy_factory = await _proxy_pool(actor_input)
        client = TravelokaClient(
            proxy_url=proxy_url, proxy_factory=proxy_factory,
            locale=actor_input.get("locale") or "en-id",
            currency=actor_input.get("currency") or "IDR",
            request_delay=float(actor_input.get("requestDelaySeconds") or 0.6))

        now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        try:
            client.bootstrap()
        except TravelokaError as exc:
            await Actor.push_data({"recordType": "ERROR", "scrapedAt": now(),
                                   "error": f"Could not open a Traveloka session: {exc}"})
            await Actor.fail(status_message="Traveloka session bootstrap failed.")
            return

        pairs = _route_pairs(actor_input)
        if not pairs:
            await Actor.push_data({
                "recordType": "ERROR", "scrapedAt": now(),
                "error": "No routes given. Use 'routes' (for example "
                         "Jakarta-Bandung) or the origin/destination fields."})
            await Actor.fail(status_message="No routes to monitor.")
            return

        travel_dates = _dates(actor_input)
        logger.info("Monitoring %d route(s) across %d date(s).",
                    len(pairs), len(travel_dates))

        # Resolve each place once, not once per date.
        resolved: dict[str, dict | None] = {}

        async def place(query: str):
            if query not in resolved:
                try:
                    resolved[query] = await resolve_location(client, query)
                except TravelokaError as exc:
                    logger.warning("Autocomplete failed for %r: %s", query, exc)
                    resolved[query] = None
            return resolved[query]

        searches = failed = 0
        total_departures = 0

        for origin_query, destination_query in pairs:
            origin = await place(origin_query)
            destination = await place(destination_query)
            if not origin or not destination:
                missing = origin_query if not origin else destination_query
                await Actor.push_data({
                    "recordType": "NOT_FOUND", "scrapedAt": now(),
                    "originQuery": origin_query,
                    "destinationQuery": destination_query,
                    "error": f"Traveloka has no bus location matching {missing!r}."})
                failed += 1
                continue

            route = {
                "originCode": origin["code"], "originType": origin["type"],
                "destinationCode": destination["code"],
                "destinationType": destination["type"],
                "originQuery": origin_query, "destinationQuery": destination_query,
                "label": f"{origin['label']} - {destination['label']}",
            }

            for travel_date in travel_dates:
                try:
                    departures, raw_count = await search_departures(
                        client, route, travel_date, adults, max_departures,
                        dedupe, product_types)
                except GateError as exc:
                    await Actor.push_data({
                        "recordType": "GATED", "scrapedAt": now(),
                        "routeQuery": route["label"],
                        "searchDate": travel_date.isoformat(),
                        "error": str(exc)})
                    failed += 1
                    continue
                except TravelokaError as exc:
                    await Actor.push_data({
                        "recordType": "NO_SERVICE", "scrapedAt": now(),
                        "routeQuery": route["label"],
                        "originQuery": origin_query,
                        "destinationQuery": destination_query,
                        "searchDate": travel_date.isoformat(),
                        "error": str(exc)})
                    failed += 1
                    continue

                searches += 1
                total_departures += len(departures)

                if want_summary:
                    summary = summarise_route(departures, route,
                                              travel_date.isoformat(), raw_count)
                    summary["scrapedAt"] = now()
                    await Actor.push_data(summary)

                if want_departures:
                    for departure in departures:
                        departure["scrapedAt"] = now()
                        await Actor.push_data(departure)

                logger.info("%s on %s: %d departures kept (of %d raw).",
                            route["label"], travel_date.isoformat(),
                            len(departures), raw_count)

        await Actor.set_status_message(
            f"{searches} search(es) done, {total_departures} departures collected, "
            f"{failed} failed.")
