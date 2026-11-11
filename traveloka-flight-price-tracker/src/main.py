"""Traveloka Flight Price Tracker -- actor entry point."""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from apify import Actor

from src.client import GateError, TravelokaClient, TravelokaError
from src.constants import MAX_WINDOW_DAYS, SEAT_CLASSES
from src.flights import monthly_curve, price_grid, resolve_airport, summarise

logger = logging.getLogger(__name__)


def _parse_date(value: str | None, fallback_offset: int) -> dt.date:
    if value:
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            logger.warning("Date %r is not YYYY-MM-DD; using the default.", value)
    return dt.date.today() + dt.timedelta(days=fallback_offset)


def _routes(actor_input: dict) -> list[tuple[str, str]]:
    """Accept either paired lists or 'CGK-DPS' style strings."""
    routes: list[tuple[str, str]] = []
    for raw in actor_input.get("routes") or []:
        text = (raw.get("route") if isinstance(raw, dict) else str(raw or "")).strip()
        if not text:
            continue
        for sep in ("->", "-->", " to ", "-", ">"):
            if sep in text:
                origin, _, destination = text.partition(sep)
                if origin.strip() and destination.strip():
                    routes.append((origin.strip(), destination.strip()))
                break
        else:
            logger.warning("Route %r has no separator (use 'CGK-DPS'); skipping.",
                           text)
    origin_one = (actor_input.get("origin") or "").strip()
    dest_one = (actor_input.get("destination") or "").strip()
    if origin_one and dest_one:
        routes.append((origin_one, dest_one))
    return routes


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
        seat_class = (actor_input.get("seatClass") or "ECONOMY").upper()
        if seat_class not in SEAT_CLASSES:
            logger.warning("Unknown seat class %r; using ECONOMY.", seat_class)
            seat_class = "ECONOMY"

        adults = int(actor_input.get("adults") or 1)
        children = int(actor_input.get("children") or 0)
        infants = int(actor_input.get("infants") or 0)
        threshold_raw = actor_input.get("priceThreshold")
        try:
            threshold = float(threshold_raw) if threshold_raw not in (None, "") else None
        except (TypeError, ValueError):
            logger.warning("priceThreshold %r is not a number; ignoring.", threshold_raw)
            threshold = None

        want_monthly = bool(actor_input.get("includeMonthlyCurve", True))
        want_grid = bool(actor_input.get("includeDateGrid", True))
        depart_start = _parse_date(actor_input.get("departDate"), 30)
        return_start = _parse_date(actor_input.get("returnDate"), 37)
        depart_days = max(1, min(int(actor_input.get("departWindowDays") or 10),
                                 MAX_WINDOW_DAYS))
        return_days = max(1, min(int(actor_input.get("returnWindowDays") or 10),
                                 MAX_WINDOW_DAYS))
        journey_type = "TWO_WAY" if actor_input.get("roundTrip", True) else "ONE_WAY"

        proxy_url, proxy_factory = await _proxy_pool(actor_input)

        client = TravelokaClient(
            proxy_url=proxy_url, proxy_factory=proxy_factory,
            locale=locale, currency=currency,
            request_delay=float(actor_input.get("requestDelaySeconds") or 0.4))

        now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        try:
            client.bootstrap()
        except TravelokaError as exc:
            await Actor.push_data({"recordType": "ERROR", "scrapedAt": now(),
                                   "error": f"Could not open a Traveloka session: {exc}"})
            await Actor.fail(status_message="Traveloka session bootstrap failed.")
            return

        routes = _routes(actor_input)
        if not routes:
            await Actor.push_data({
                "recordType": "ERROR", "scrapedAt": now(),
                "error": "No routes given. Use 'routes' (for example CGK-DPS) or "
                         "the origin/destination fields."})
            await Actor.fail(status_message="No routes to track.")
            return

        logger.info("Tracking %d route(s), seat class %s, %s.",
                    len(routes), seat_class,
                    "round trip" if journey_type == "TWO_WAY" else "one way")

        tracked = failed = alerts = 0
        for origin_query, dest_query in routes:
            record = {"recordType": "ROUTE", "scrapedAt": now(),
                      "originQuery": origin_query, "destinationQuery": dest_query,
                      "seatClass": seat_class, "currency": currency,
                      "journeyType": journey_type, "warnings": []}
            try:
                origin = await resolve_airport(client, origin_query)
                destination = await resolve_airport(client, dest_query)
            except (GateError, TravelokaError) as exc:
                record.update({"recordType": "ERROR", "error": str(exc)})
                await Actor.push_data(record)
                failed += 1
                continue

            if not origin or not destination:
                missing = origin_query if not origin else dest_query
                record.update({
                    "recordType": "NOT_FOUND",
                    "error": f"Could not resolve {missing!r} to an airport. "
                             "Try the IATA code, for example CGK."})
                await Actor.push_data(record)
                failed += 1
                continue

            record.update({
                "originCode": origin["code"], "originName": origin["name"],
                "originCountry": origin["country"],
                "destinationCode": destination["code"],
                "destinationName": destination["name"],
                "destinationCountry": destination["country"],
                "route": f"{origin['code']}-{destination['code']}",
            })

            monthly: list[dict] = []
            grid: list[dict] = []

            if want_monthly:
                try:
                    monthly = await monthly_curve(client, origin, destination,
                                                  journey_type, depart_start)
                except GateError as exc:
                    record["warnings"].append(str(exc))
                except TravelokaError as exc:
                    record["warnings"].append(f"monthly curve unavailable: {exc}")

            if want_grid:
                try:
                    grid = await price_grid(
                        client, origin, destination, depart_start, depart_days,
                        return_start, return_days, seat_class, adults, children,
                        infants, locale)
                except GateError as exc:
                    record["warnings"].append(str(exc))
                except TravelokaError as exc:
                    record["warnings"].append(f"date grid unavailable: {exc}")

            record["monthlyCurve"] = monthly
            record["dateGrid"] = grid
            record["summary"] = summarise(monthly, grid, threshold)

            if not monthly and not grid:
                record["recordType"] = "NO_FARES"
                record.setdefault("error",
                                  "Traveloka returned no fares for this route in "
                                  "the requested window.")
                failed += 1
            else:
                tracked += 1
                if record["summary"]["belowThreshold"]:
                    alerts += 1
                    logger.info("ALERT %s: lowest fare %s is at or below %s.",
                                record["route"], record["summary"]["lowestFare"],
                                threshold)

            await Actor.push_data(record)

        message = f"Tracked {tracked} route(s), {failed} without fares."
        if threshold is not None:
            # `:g` renders large IDR thresholds as 3e+06; spell them out instead.
            message += f" {alerts} below the {threshold:,.0f} threshold."
        await Actor.set_status_message(message)
