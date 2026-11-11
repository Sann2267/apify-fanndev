"""Actor entry point: Amazon customer insights and aspect sentiment."""

import asyncio
import logging
import random
from datetime import datetime, timezone

from apify import Actor

from src.client import AmazonClient, Blocked
from src.constants import (
    DOMAINS,
    RECORD_DIAGNOSTIC,
    VERIFIED_MARKETPLACES,
)
from src.insights import (
    InvalidInput,
    aspect_records,
    clean_asin,
    looks_reduced,
    parse_insights,
    product_url,
)
from src.input_errors import input_error

logger = logging.getLogger(__name__)

DEFAULT_ASINS = ["B00XIKPUK4", "B087F16GKW", "B07ZPKN6YR"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def diagnostic_record(asin: str, marketplace: str, error: str, detail: str) -> dict:
    """Emitted instead of silently dropping a blocked or invalid input."""
    return {
        "_input": asin,
        "_source": "S0-diagnostic",
        "_scrapedAt": _now(),
        "recordType": RECORD_DIAGNOSTIC,
        "asin": asin,
        "marketplace": marketplace,
        "productUrl": product_url(marketplace, asin) if marketplace in DOMAINS else None,
        "hasInsights": False,
        "_error": error,
        "_errorDetail": detail[:500],
    }


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        marketplace = str(actor_input.get("marketplace") or "com").strip()
        if marketplace not in DOMAINS:
            raise input_error(
                f"marketplace {marketplace!r} is not supported; expected one of "
                f"{', '.join(sorted(DOMAINS))}"
            )
        if marketplace not in VERIFIED_MARKETPLACES:
            Actor.log.warning(
                "marketplace %r could not be verified during development (the "
                "development IP was bot-walled there). Use a residential proxy "
                "in that country; aspect labels may also be localized.",
                marketplace,
            )

        raw_asins = actor_input.get("asins") or DEFAULT_ASINS
        if isinstance(raw_asins, str):
            raw_asins = [raw_asins]

        emit_aspect_rows = bool(actor_input.get("emitAspectRows", True))
        gaps_only = bool(actor_input.get("contentGapsOnly", False))
        min_mentions = int(actor_input.get("minMentions") or 0)
        retries = int(actor_input.get("emptyInsightRetries", 2) or 0)
        delay_seconds = float(actor_input.get("delaySeconds") or 2.0)

        asins, rejected = [], []
        for raw in raw_asins:
            try:
                value = clean_asin(raw)
            except InvalidInput as exc:
                rejected.append((str(raw)[:60], str(exc)))
            else:
                if value not in asins:
                    asins.append(value)

        for raw, reason in rejected:
            Actor.log.warning("skipping invalid input %r: %s", raw, reason)
            await Actor.push_data(
                diagnostic_record(raw, marketplace, "INVALID_ASIN", reason)
            )

        if not asins:
            Actor.log.error("no usable ASINs in input")
            return

        try:
            proxy_configuration = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001 -- proxy is optional locally
            Actor.log.warning("could not create proxy configuration: %s", exc)
            proxy_configuration = None
        proxy_url = await proxy_configuration.new_url() if proxy_configuration else None
        if not proxy_url:
            Actor.log.warning(
                "running without a proxy -- Amazon bot-walls repeated product-page "
                "fetches from one IP; residential proxy is recommended"
            )

        client = AmazonClient(marketplace=marketplace, proxy_url=proxy_url,
                              proxy_configuration=proxy_configuration)
        stats = {"ok": 0, "blocked": 0, "with_insights": 0, "aspects": 0,
                 "gaps": 0, "rescued": 0, "reduced": 0}

        try:
            for index, asin in enumerate(asins):
                try:
                    body = await client.get_product(product_url(marketplace, asin))
                except Blocked as exc:
                    stats["blocked"] += 1
                    Actor.log.warning("%s: %s", asin, exc)
                    await Actor.push_data(
                        diagnostic_record(asin, marketplace, "BLOCKED", str(exc))
                    )
                    continue

                product = parse_insights(body, asin, marketplace)

                # A cleanly parsed page with no widget is not an answer yet:
                # Amazon withholds the widget from some exit IPs, and the
                # reduced page is full size, so nothing upstream can catch
                # it. Rotate the exit and look again before believing that a
                # heavily reviewed product has no published opinions.
                for attempt in range(retries):
                    if not looks_reduced(product):
                        break
                    if not await client.rotate_session():
                        Actor.log.warning(
                            "%s: no insight widget and %s ratings, but there is "
                            "no proxy to rotate -- reporting as-is",
                            asin, product["reviewCount"])
                        break
                    Actor.log.info(
                        "%s: no insight widget despite %s ratings -- retrying on a "
                        "fresh exit IP (%s/%s)",
                        asin, product["reviewCount"], attempt + 1, retries)
                    await asyncio.sleep(1.5 + random.uniform(0, 1.0))
                    try:
                        body = await client.get_product(product_url(marketplace, asin))
                    except Blocked as exc:
                        # The first response was a real product page, so keep
                        # it rather than downgrading the row to a diagnostic.
                        Actor.log.warning("%s: retry blocked (%s)", asin, exc)
                        break
                    product = parse_insights(body, asin, marketplace)
                    if product["hasInsights"]:
                        stats["rescued"] += 1
                        break
                if looks_reduced(product):
                    stats["reduced"] += 1

                stats["ok"] += 1
                if product["hasInsights"]:
                    stats["with_insights"] += 1
                stats["gaps"] += product["gapAspectCount"]

                if not gaps_only:
                    await Actor.push_data(product)

                if emit_aspect_rows:
                    rows = aspect_records(product)
                    if gaps_only:
                        rows = [r for r in rows if r["isContentGap"]]
                    if min_mentions:
                        # Rows with an unknown count are kept: absent is not
                        # the same as below-threshold.
                        rows = [
                            r for r in rows
                            if r["mentions"] is None or r["mentions"] >= min_mentions
                        ]
                    for row in rows:
                        await Actor.push_data(row)
                    stats["aspects"] += len(rows)

                Actor.log.info(
                    "%s %s | %s aspects (%s gaps) | summary=%s",
                    asin,
                    (product["title"] or "?")[:40],
                    product["aspectCount"] or 0,
                    product["gapAspectCount"],
                    "yes" if product["aiSummary"] else "no",
                )
                if product["contentGaps"]:
                    Actor.log.info("    gaps: %s", ", ".join(product["contentGaps"]))

                if index < len(asins) - 1 and delay_seconds > 0:
                    await asyncio.sleep(delay_seconds + random.uniform(0, 0.8))
        finally:
            await client.close()

        Actor.log.info(
            "done: %s scraped (%s carried insights, %s rescued by rotating the "
            "exit IP), %s aspect rows, %s content gaps, %s blocked",
            stats["ok"], stats["with_insights"], stats["rescued"],
            stats["aspects"], stats["gaps"], stats["blocked"],
        )
        if stats["reduced"]:
            Actor.log.warning(
                "%s ASIN(s) still returned no insight widget despite a review "
                "count that says they should have one. Those rows are reduced "
                "pages, not products without opinions -- raise "
                "emptyInsightRetries or use a different proxy country.",
                stats["reduced"],
            )
        if stats["ok"] and not stats["with_insights"]:
            Actor.log.warning(
                "no insight widget was served for any ASIN -- this is normal for "
                "products with very few reviews, but check the proxy country if "
                "every ASIN came back empty"
            )
