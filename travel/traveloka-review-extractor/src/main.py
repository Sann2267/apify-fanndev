"""Traveloka Review & Sentiment Extractor -- actor entry point."""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from apify import Actor

from src.client import GateError, TravelokaClient, TravelokaError
from src.constants import (
    FORMAT_FILTERS,
    MAX_PAGE_SIZE,
    PAGE_SIZE,
    PRODUCT_PRESETS,
    RATING_FILTERS,
    SORT_VALUES,
)
from src.reviews import (
    detect_product,
    fetch_aggregate,
    fetch_count,
    fetch_rating_tags,
    fetch_reviews,
    load_config_ids,
    object_id_from_url,
    resolve_config,
)

logger = logging.getLogger(__name__)


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


def _targets(actor_input: dict, default_product: str) -> list[dict]:
    """Resolve every input URL/ID to an (objectId, product) pair."""
    targets: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(object_id: str | None, product: str, source: str) -> None:
        if not object_id:
            return
        key = (object_id, product)
        if key in seen:
            return
        seen.add(key)
        targets.append({"objectId": object_id, "product": product, "source": source})

    for raw in actor_input.get("startUrls") or []:
        url = raw.get("url") if isinstance(raw, dict) else raw
        url = str(url or "")
        object_id = object_id_from_url(url)
        if not object_id:
            logger.warning("No numeric ID in %r; skipping.", url)
            continue
        product = detect_product(url) or default_product
        add(object_id, product, url)

    for raw in actor_input.get("objectIds") or []:
        add(object_id_from_url(str(raw)), default_product, "input:id")

    return targets


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        default_product = (actor_input.get("productType") or "hotel").lower()
        if default_product not in PRODUCT_PRESETS:
            logger.warning("Unknown productType %r; using 'hotel'.", default_product)
            default_product = "hotel"

        sort = actor_input.get("sortBy") or "SORT_CREATED_DESCENDING"
        if sort not in SORT_VALUES:
            logger.warning("Unknown sortBy %r; using newest first.", sort)
            sort = "SORT_CREATED_DESCENDING"

        rating_filter = actor_input.get("ratingFilter") or "RATING_VALUE_ALL"
        format_filter = actor_input.get("formatFilter") or "FORMAT_VALUE_ALL"
        review_filter: dict = {}
        if rating_filter in RATING_FILTERS and rating_filter != "RATING_VALUE_ALL":
            review_filter["rating"] = rating_filter
        if format_filter in FORMAT_FILTERS and format_filter != "FORMAT_VALUE_ALL":
            review_filter["format"] = format_filter

        max_reviews = int(actor_input.get("maxReviewsPerObject") or 200)
        page_size = max(1, min(int(actor_input.get("pageSize") or PAGE_SIZE),
                               MAX_PAGE_SIZE))
        want_summary = bool(actor_input.get("includeSummaryRecord", True))
        want_tags = bool(actor_input.get("includeRatingTags", True))

        proxy_url, proxy_factory = await _proxy_pool(actor_input)
        client = TravelokaClient(
            proxy_url=proxy_url, proxy_factory=proxy_factory,
            locale=actor_input.get("locale") or "en-id",
            currency=actor_input.get("currency") or "IDR",
            request_delay=float(actor_input.get("requestDelaySeconds") or 0.4))

        now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        try:
            client.bootstrap()
        except TravelokaError as exc:
            await Actor.push_data({"recordType": "ERROR", "scrapedAt": now(),
                                   "error": f"Could not open a Traveloka session: {exc}"})
            await Actor.fail(status_message="Traveloka session bootstrap failed.")
            return

        targets = _targets(actor_input, default_product)
        if not targets:
            await Actor.push_data({
                "recordType": "ERROR", "scrapedAt": now(),
                "error": "No objects to scrape. Supply startUrls (hotel or activity "
                         "pages) or objectIds."})
            await Actor.fail(status_message="No review targets resolved.")
            return

        config_ids = await load_config_ids(client)
        logger.info("Extracting reviews for %d object(s), sorted by %s.",
                    len(targets), sort)

        total_reviews = 0
        done = failed = 0
        for target in targets:
            object_id = target["objectId"]
            product = target["product"]
            try:
                config_id, product_type, referer = resolve_config(product, config_ids)
            except TravelokaError as exc:
                await Actor.push_data({
                    "recordType": "ERROR", "objectId": object_id,
                    "scrapedAt": now(), "error": str(exc)})
                failed += 1
                continue

            summary: dict = {
                "recordType": "OBJECT_SUMMARY",
                "objectId": object_id,
                "product": product,
                "productType": product_type,
                "sourceUrl": target["source"] if target["source"].startswith("http")
                else None,
                "scrapedAt": now(),
                "warnings": [],
            }

            aggregate = {}
            try:
                aggregate = await fetch_aggregate(client, object_id, config_id,
                                                  product_type, referer)
                summary.update(aggregate)
            except GateError as exc:
                summary.update({"recordType": "GATED", "error": str(exc)})
                await Actor.push_data(summary)
                failed += 1
                continue
            except TravelokaError as exc:
                summary["warnings"].append(f"aggregate unavailable: {exc}")

            object_name = aggregate.get("objectName")

            if want_tags:
                try:
                    summary["ratingTags"] = await fetch_rating_tags(
                        client, object_id, config_id, product_type, referer)
                except TravelokaError as exc:
                    summary["warnings"].append(f"rating tags unavailable: {exc}")

            try:
                summary["matchingReviewCount"] = await fetch_count(
                    client, object_id, config_id, product_type, referer,
                    review_filter)
            except TravelokaError as exc:
                summary["warnings"].append(f"review count unavailable: {exc}")

            try:
                reviews = await fetch_reviews(
                    client, object_id, config_id, product_type, referer,
                    max_reviews, page_size, sort, review_filter,
                    list(actor_input.get("ratingTagIds") or []), object_name)
            except GateError as exc:
                summary.update({"recordType": "GATED", "error": str(exc)})
                await Actor.push_data(summary)
                failed += 1
                continue
            except TravelokaError as exc:
                summary.update({"recordType": "ERROR", "error": str(exc)})
                await Actor.push_data(summary)
                failed += 1
                continue

            summary["reviewsCollected"] = len(reviews)
            if not aggregate and not reviews:
                summary["recordType"] = "NOT_FOUND"
                summary.setdefault(
                    "error",
                    f"No reviews or rating summary for object {object_id}. Check "
                    "that productType matches the URL you supplied.")
                failed += 1
            else:
                done += 1

            if want_summary:
                await Actor.push_data(summary)

            for review in reviews:
                review["product"] = product
                review["scrapedAt"] = summary["scrapedAt"]
                await Actor.push_data(review)
            total_reviews += len(reviews)

            logger.info("%s (%s): %d reviews of %s total.",
                        object_name or object_id, product, len(reviews),
                        aggregate.get("totalReviewCount"))

        await Actor.set_status_message(
            f"Extracted {total_reviews} reviews from {done} object(s); "
            f"{failed} failed.")
