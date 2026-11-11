"""Blibli Drop-shipper Data Sync -- Apify Actor entrypoint."""

import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import (
    STATE_KEY,
    STATE_STORE_NAME,
    SYNC_NOT_FOUND,
)
from src.sync import InvalidInput, detect_changes, resolve_sku, snapshot_entry, sync_skus

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_items = actor_input.get("productUrls") or []
        detailed = bool(actor_input.get("detailedMode"))
        verify_missing = actor_input.get("verifyMissing", True)
        track_changes = actor_input.get("trackChanges", True)
        changed_only = bool(actor_input.get("onlyChangedItems"))
        state_store_name = actor_input.get("stateStoreName") or STATE_STORE_NAME

        proxy_config = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)

        proxy_url = await proxy_config.new_url() if proxy_config else None
        new_proxy_url = proxy_config.new_url if proxy_config else None
        if not proxy_url:
            Actor.log.warning(
                "Running without a proxy. Blibli is behind Cloudflare and throttles "
                "sustained traffic from one IP -- residential proxy is recommended for "
                "scheduled syncs."
            )

        client = BlibliClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        pushed = 0
        stats = {"ok": 0, "notFound": 0, "changed": 0, "skipped": 0}

        try:
            if not raw_items:
                raise InvalidInput(
                    "`productUrls` is empty. Provide the Blibli product URLs or SKUs you "
                    "resell, e.g. [\"COP-60023-00933\"]."
                )

            skus: list[str] = []
            for raw in raw_items:
                try:
                    sku = resolve_sku(raw)
                except InvalidInput as exc:
                    Actor.log.error("Skipping %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": "none", "syncStatus": "INVALID_INPUT",
                        "_error": "INVALID_INPUT", "_errorDetail": str(exc),
                    })
                    pushed += 1
                else:
                    if sku not in skus:
                        skus.append(sku)
            if not skus:
                raise InvalidInput("No usable SKUs among the provided inputs.")

            # Previous snapshot lives in a named key-value store so it
            # survives between scheduled runs; the default dataset does not.
            previous: dict = {}
            store = None
            if track_changes:
                store = await Actor.open_key_value_store(name=state_store_name)
                previous = await store.get_value(STATE_KEY) or {}
                Actor.log.info(
                    "Loaded snapshot '%s' with %d previously-seen SKU(s)",
                    state_store_name, len(previous),
                )

            Actor.log.info(
                "Syncing %d SKU(s), detailed=%s, trackChanges=%s", len(skus), detailed,
                track_changes,
            )

            snapshot: dict = {}
            async for record in sync_skus(client, skus, detailed, verify_missing):
                sku = record["sku"]
                if track_changes:
                    record = detect_changes(record, previous.get(sku))
                    snapshot[sku] = snapshot_entry(record)
                    if record.get("hasChanged"):
                        stats["changed"] += 1

                if record.get("syncStatus") == SYNC_NOT_FOUND:
                    stats["notFound"] += 1
                else:
                    stats["ok"] += 1

                if changed_only and track_changes and not record.get("hasChanged"):
                    stats["skipped"] += 1
                    continue

                await Actor.push_data(record)
                pushed += 1

            if track_changes and store is not None:
                # Carry forward SKUs that were not part of this run so a
                # partial sync does not erase their history.
                merged = {**previous, **snapshot}
                await store.set_value(STATE_KEY, merged)
                Actor.log.info("Snapshot saved: %d SKU(s) tracked", len(merged))

        except (InvalidInput, BlockedError, UpstreamShapeError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": "none", "syncStatus": error_kind,
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0 and not stats["skipped"]:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": "none", "syncStatus": "EMPTY_RESULT",
                "_error": "EMPTY_RESULT",
                "_errorDetail": "No SKU resolved. Check the product URLs or SKUs supplied.",
            })
        elif pushed == 0:
            Actor.log.info("Nothing changed since the last run -- no rows emitted.")

        Actor.log.info(
            "Done -- %d pushed | %d ok, %d not found, %d changed, %d unchanged-skipped",
            pushed, stats["ok"], stats["notFound"], stats["changed"], stats["skipped"],
        )
        await Actor.set_status_message(
            f"{stats['ok']} ok, {stats['changed']} changed, {stats['notFound']} not found"
        )
