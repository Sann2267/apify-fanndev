"""Actor entry point: ASIN lookup, Buy Box capture and change monitoring."""

import asyncio
import logging
import random
from datetime import datetime, timezone

from apify import Actor

from src.client import AmazonClient, Blocked
from src.constants import (
    DEFAULT_SNAPSHOT_STORE,
    DOMAINS,
    RECORD_DIAGNOSTIC,
)
from src.product import (
    InvalidInput,
    clean_asin,
    detect_changes,
    parse_product,
    product_url,
    snapshot_key,
)
from src.input_errors import input_error

logger = logging.getLogger(__name__)

DEFAULT_ASINS = ["B00XIKPUK4", "B06XX65GS1", "B0BJLBD427"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def diagnostic_record(asin: str, marketplace: str, error: str, detail: str) -> dict:
    """Emitted instead of silently dropping a blocked ASIN.

    A run that quietly returns 8 rows for 10 inputs looks like the products
    do not exist. This makes the difference visible in the dataset itself.
    """
    return {
        "_input": asin,
        "_source": "S0-diagnostic",
        "_scrapedAt": _now(),
        "recordType": RECORD_DIAGNOSTIC,
        "asin": asin,
        "marketplace": marketplace,
        "productUrl": product_url(marketplace, asin) if marketplace in DOMAINS else None,
        "buyBoxDataAvailable": False,
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

        raw_asins = actor_input.get("asins") or DEFAULT_ASINS
        if isinstance(raw_asins, str):
            raw_asins = [raw_asins]

        include_variations = bool(actor_input.get("includeVariations", True))
        expand_variations = bool(actor_input.get("expandVariations", False))
        max_children = int(actor_input.get("maxVariationsPerAsin") or 5)
        track_changes = bool(actor_input.get("trackChanges", False))
        snapshot_name = str(
            actor_input.get("snapshotName") or DEFAULT_SNAPSHOT_STORE
        ).strip() or DEFAULT_SNAPSHOT_STORE
        delay_seconds = float(actor_input.get("delaySeconds") or 2.0)
        buybox_retries = int(actor_input.get("buyBoxRetries", 2) or 0)

        # Validate every ASIN up front so a typo is reported as a row rather
        # than aborting a long run halfway through.
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
                "running without a proxy -- Amazon blocks repeated product-page "
                "fetches from one IP quickly; residential proxy is recommended"
            )

        store = None
        previous = {}
        if track_changes:
            store = await Actor.open_key_value_store(name=snapshot_name)
            previous = await store.get_value("snapshot") or {}
            Actor.log.info(
                "change tracking on -- %s ASIN(s) in snapshot %r",
                len(previous), snapshot_name,
            )

        client = AmazonClient(marketplace=marketplace, proxy_url=proxy_url,
                              proxy_configuration=proxy_configuration)
        snapshot = dict(previous)
        stats = {"ok": 0, "blocked": 0, "buybox": 0, "children": 0, "recovered": 0}

        try:
            queue = [(asin, False) for asin in asins]
            seen = set(asins)
            index = 0

            while index < len(queue):
                asin, is_child = queue[index]
                index += 1
                try:
                    body = await client.get_product(product_url(marketplace, asin))
                except Blocked as exc:
                    stats["blocked"] += 1
                    Actor.log.warning("%s: %s", asin, exc)
                    await Actor.push_data(
                        diagnostic_record(asin, marketplace, "BLOCKED", str(exc))
                    )
                    continue

                record = parse_product(
                    body, asin, marketplace, want_variations=include_variations
                )

                # Whether Amazon serves the offer block tracks the exit IP,
                # not the ASIN: an ASIN that came back Buy-Box-less on a home
                # IP returned a full page through a residential proxy, and
                # vice versa. So a missing Buy Box is worth retrying on a
                # fresh proxy session -- this is the difference between ~50%
                # and ~80% seller coverage.
                attempts = 0
                while (
                    buybox_retries
                    and not record["buyBoxDataAvailable"]
                    and attempts < buybox_retries
                    and await client.rotate_session()
                ):
                    attempts += 1
                    Actor.log.info(
                        "%s: no Buy Box served, retrying on a fresh proxy session (%s/%s)",
                        asin, attempts, buybox_retries,
                    )
                    try:
                        retry_body = await client.get_product(product_url(marketplace, asin))
                    except Blocked as exc:
                        Actor.log.warning("%s: Buy Box retry blocked: %s", asin, exc)
                        break
                    retry_record = parse_product(
                        retry_body, asin, marketplace, want_variations=include_variations
                    )
                    # Only accept the retry if it actually carries more; never
                    # trade a good response for an emptier one.
                    if retry_record["buyBoxDataAvailable"] or (
                        retry_record["price"] is not None and record["price"] is None
                    ):
                        record = retry_record
                        record["_source"] = f"S2-dp-page-retry{attempts}"
                        stats["recovered"] += 1
                        break

                record["isVariationChild"] = is_child
                stats["ok"] += 1
                if record["buyBoxDataAvailable"]:
                    stats["buybox"] += 1

                if track_changes:
                    record.update(detect_changes(record, previous.get(asin)))
                    snapshot[asin] = snapshot_key(record)
                else:
                    record.update({
                        "changeType": None, "changes": None, "previousPrice": None,
                        "previousSellerId": None, "priceDelta": None,
                        "priceDeltaPercent": None, "previousScrapedAt": None,
                    })

                await Actor.push_data(record)
                Actor.log.info(
                    "%s %s | %s%s | seller=%s | %s",
                    asin,
                    (record["title"] or "?")[:44],
                    record["currency"] or "",
                    record["price"],
                    record["buyBoxSellerName"]
                    or record["buyBoxSellerId"]
                    or "not served",
                    record["changeType"] or "-",
                )

                # Children are queued only from top-level ASINs, so the walk
                # cannot fan out recursively through a whole catalogue.
                if expand_variations and not is_child and record.get("childAsins"):
                    for child in record["childAsins"][:max_children]:
                        if child not in seen:
                            seen.add(child)
                            queue.append((child, True))
                            stats["children"] += 1

                if index < len(queue) and delay_seconds > 0:
                    await asyncio.sleep(delay_seconds + random.uniform(0, 0.8))

            if track_changes and store is not None:
                await store.set_value("snapshot", snapshot)
                Actor.log.info("snapshot %r now holds %s ASIN(s)", snapshot_name, len(snapshot))
        finally:
            await client.close()

        Actor.log.info(
            "done: %s scraped (%s with Buy Box seller, %s recovered by session retry), "
            "%s blocked, %s variation children",
            stats["ok"], stats["buybox"], stats["recovered"],
            stats["blocked"], stats["children"],
        )
        if stats["ok"] and not stats["buybox"]:
            Actor.log.warning(
                "no Buy Box seller was served for any ASIN this run -- Amazon omits "
                "that block for roughly half of anonymous product-page requests; "
                "buyBoxDataAvailable=false marks those rows"
            )
