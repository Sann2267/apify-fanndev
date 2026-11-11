"""Blibli Merchant Profile & Inventory Scraper -- Apify Actor entrypoint."""

import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.merchant import (
    InvalidTarget,
    StoreNotFound,
    count_products,
    fetch_catalog,
    fetch_followers,
    fetch_profile,
    fetch_review_summary,
    fetch_vouchers,
    profile_record,
    resolve_store,
)

logger = logging.getLogger(__name__)

COVERAGE_LEVELS = ("standard", "deep")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_targets = actor_input.get("storeUrls") or []
        include_products = actor_input.get("includeProducts", True)
        coverage = actor_input.get("catalogCoverage", "standard")
        max_products = actor_input.get("maxProductsPerStore") or 0
        include_vouchers = actor_input.get("includeVouchers", True)
        include_reviews = actor_input.get("includeReviewStats", True)

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
        failed = 0

        try:
            if not raw_targets:
                raise InvalidTarget(
                    "`storeUrls` is empty. Provide at least one Blibli store URL, store code, "
                    "or any product URL/SKU from the store."
                )
            if coverage not in COVERAGE_LEVELS:
                raise InvalidTarget(
                    f"Unknown catalogCoverage {coverage!r}. Expected one of "
                    f"{list(COVERAGE_LEVELS)}."
                )

            # Resolve up front so a typo surfaces before any requests are spent.
            codes = []
            for raw in raw_targets:
                try:
                    code = resolve_store(raw)
                except InvalidTarget as exc:
                    Actor.log.error("Skipping unusable target %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": "none", "recordType": "ERROR",
                        "_error": "INVALID_TARGET", "_errorDetail": str(exc),
                    })
                    pushed += 1
                    failed += 1
                else:
                    if code not in codes:
                        codes.append(code)
            if not codes:
                raise InvalidTarget("No usable stores among the provided inputs.")

            Actor.log.info("Mapping %d store(s), catalogCoverage=%s", len(codes), coverage)

            for code in codes:
                try:
                    profile = await fetch_profile(client, code)
                    followers = await fetch_followers(client, code)
                    review_summary = await fetch_review_summary(client, code) if include_reviews else {}
                    vouchers = await fetch_vouchers(client, code) if include_vouchers else []
                    total_products = await count_products(client, code)

                    record = profile_record(
                        code, profile, followers, review_summary, vouchers, total_products
                    )
                    await Actor.push_data(record)
                    pushed += 1
                    Actor.log.info(
                        "%s | %s | badge=%s respond=%s | %s products, %s followers, "
                        "%s reviews (avg %s)",
                        code, record.get("merchantName"), record.get("badgeId"),
                        record.get("respondTimeRating"), total_products, followers,
                        record.get("totalReviews"), record.get("averageRating"),
                    )

                    if include_products:
                        async for product in fetch_catalog(
                            client, code, coverage, max_products, record.get("merchantName")
                        ):
                            await Actor.push_data(product)
                            pushed += 1

                except (BlockedError, UpstreamShapeError, StoreNotFound) as exc:
                    # One bad store must not sink the whole run.
                    failed += 1
                    Actor.log.error("Store %s failed: %s", code, exc)
                    await Actor.push_data({
                        "_input": code, "_source": "none", "recordType": "ERROR",
                        "_error": {
                            BlockedError: "BLOCKED_AFTER_RETRIES",
                            UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
                            StoreNotFound: "STORE_NOT_FOUND",
                        }[type(exc)],
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
                "_errorDetail": "No store data returned. Check the store codes are valid.",
            })

        Actor.log.info("Done -- %d record(s) pushed, %d store(s) failed.", pushed, failed)
        await Actor.set_status_message(f"{pushed} record(s), {failed} store(s) failed")
