"""Blibli Store Review & Sentiment Analyzer -- Apify Actor entrypoint."""

import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import SORT_OPTIONS, TYPE_MERCHANT
from src.reviews import (
    InvalidTarget,
    fetch_merchant_name,
    fetch_store_products,
    fetch_summary,
    resolve_target,
    run_target,
    summary_record,
)

logger = logging.getLogger(__name__)

COVERAGE_LEVELS = ("standard", "deep", "maximum")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_targets = actor_input.get("storeUrls") or []
        coverage = actor_input.get("coverage", "deep")
        sort_by = actor_input.get("sortBy", "LATEST")
        max_reviews = actor_input.get("maxReviewsPerTarget") or 0
        min_rating = actor_input.get("minRating") or 0
        with_media_only = bool(actor_input.get("onlyWithMedia"))
        only_with_text = actor_input.get("onlyWithText", True)
        include_summary = actor_input.get("includeSummary", True)
        product_breakdown = bool(actor_input.get("productBreakdown"))
        max_products = actor_input.get("maxProductsPerStore") or 50

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
                "Running without a proxy. Blibli is behind Cloudflare -- a datacenter "
                "or shared IP may be rate-limited on long runs."
            )

        client = BlibliClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        pushed = 0
        failed_targets = 0

        try:
            if not raw_targets:
                raise InvalidTarget(
                    "`storeUrls` is empty. Provide at least one Blibli store URL, store code, "
                    "product URL, product SKU, or 'brand:<name>'."
                )
            if coverage not in COVERAGE_LEVELS:
                raise InvalidTarget(
                    f"Unknown coverage {coverage!r}. Expected one of {list(COVERAGE_LEVELS)}."
                )
            if sort_by not in SORT_OPTIONS:
                raise InvalidTarget(
                    f"Unknown sortBy {sort_by!r}. Expected one of {list(SORT_OPTIONS)}."
                )

            # Resolve every target up front so a typo in one input surfaces
            # before spending any requests on the others.
            targets = []
            for raw in raw_targets:
                try:
                    targets.append(resolve_target(raw))
                except InvalidTarget as exc:
                    Actor.log.error("Skipping unusable target %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": "none", "recordType": "ERROR",
                        "_error": "INVALID_TARGET", "_errorDetail": str(exc),
                    })
                    pushed += 1
                    failed_targets += 1
            if not targets:
                raise InvalidTarget("No usable targets among the provided inputs.")

            Actor.log.info(
                "Scraping %d target(s), coverage=%s, sortBy=%s", len(targets), coverage, sort_by
            )

            for target in targets:
                # Resolved once per store and threaded through both the
                # summary row and every per-product sub-target below.
                merchant_name = None
                if target["type"] == TYPE_MERCHANT:
                    merchant_name = await fetch_merchant_name(client, target["value"])

                # Expand a store into its products only when explicitly asked:
                # per-product sweeps open a separate review window per SKU
                # (deeper coverage) but cost one request set per product.
                sub_targets = [target]
                if product_breakdown and target["type"] == TYPE_MERCHANT:
                    products = await fetch_store_products(client, target["value"], max_products)
                    Actor.log.info(
                        "productBreakdown: %s expanded to %d product(s)",
                        target["value"], len(products),
                    )
                    sub_targets += [
                        {"type": "productSku", "value": p["sku"], "label": p["sku"]}
                        for p in products
                    ]

                if include_summary:
                    try:
                        summary = await fetch_summary(client, target)
                    except (BlockedError, UpstreamShapeError) as exc:
                        Actor.log.warning("Summary failed for %s: %s", target["label"], exc)
                    else:
                        if summary:
                            record = summary_record(target, summary, merchant_name)
                            await Actor.push_data(record)
                            pushed += 1
                            Actor.log.info(
                                "%s: %s reviews, avg %s, %s%% negative",
                                target["label"], record.get("totalReviews"),
                                record.get("averageRating"), record.get("negativeSharePercent"),
                            )

                for sub in sub_targets:
                    try:
                        async for record in run_target(
                            client, sub, coverage, sort_by, max_reviews,
                            min_rating, with_media_only, merchant_name, only_with_text,
                        ):
                            await Actor.push_data(record)
                            pushed += 1
                    except (BlockedError, UpstreamShapeError) as exc:
                        # One bad target must not sink the whole run.
                        failed_targets += 1
                        Actor.log.exception("Target %s failed", sub["label"])
                        await Actor.push_data({
                            "_input": sub["label"], "_source": "none", "recordType": "ERROR",
                            "_error": (
                                "BLOCKED_AFTER_RETRIES"
                                if isinstance(exc, BlockedError)
                                else "UPSTREAM_SHAPE_CHANGED"
                            ),
                            "_errorDetail": str(exc),
                        })
                        pushed += 1

        except (InvalidTarget, BlockedError, UpstreamShapeError) as exc:
            error_kind = {
                InvalidTarget: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": "none", "recordType": "ERROR",
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": "none", "recordType": "ERROR",
                "_error": "EMPTY_RESULT",
                "_errorDetail": (
                    "No review matched. Loosen minRating, turn off onlyWithMedia, "
                    "raise coverage, or check the store actually has public reviews."
                ),
            })

        Actor.log.info("Done -- %d record(s) pushed, %d target(s) failed.", pushed, failed_targets)
        await Actor.set_status_message(f"{pushed} record(s), {failed_targets} target(s) failed")
