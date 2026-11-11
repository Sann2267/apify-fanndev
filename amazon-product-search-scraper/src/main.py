"""Actor entry point: Amazon search-results (SERP) product scraper."""

import asyncio
import logging
import random
from datetime import datetime, timezone

from apify import Actor

from src.client import AmazonClient, BlockedError, CaptchaError
from src.constants import (
    DEFAULT_DELAY_SECONDS,
    DOMAINS,
    MAX_PAGES,
    RECORD_DIAGNOSTIC,
)
from src.serp import (
    InvalidInput,
    has_next_page,
    normalise_target,
    paginate,
    parse_page,
)
from src.input_errors import input_error

logger = logging.getLogger(__name__)

DEFAULT_TARGETS = ["yoga mat", "coffee maker"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def diagnostic_record(label: str, marketplace: str, error: str, detail: str) -> dict:
    """Emitted instead of silently dropping a blocked or unusable target."""
    return {
        "_input": label,
        "_source": "S0-diagnostic",
        "_scrapedAt": _now(),
        "recordType": RECORD_DIAGNOSTIC,
        "searchTerm": label,
        "marketplace": marketplace,
        "_error": error,
        "_errorDetail": detail[:600],
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

        raw_targets = (
            actor_input.get("searchTerms")
            or actor_input.get("keywords")
            or DEFAULT_TARGETS
        )
        if isinstance(raw_targets, str):
            raw_targets = [raw_targets]

        max_pages = max(1, min(int(actor_input.get("maxPages") or 1), MAX_PAGES))
        max_items = int(actor_input.get("maxItemsPerTerm") or 0)
        include_sponsored = bool(actor_input.get("includeSponsored", True))
        delay_seconds = float(actor_input.get("delaySeconds") or DEFAULT_DELAY_SECONDS)

        targets, rejected = [], []
        for raw in raw_targets:
            try:
                targets.append(normalise_target(raw, marketplace))
            except InvalidInput as exc:
                rejected.append((str(raw)[:70], str(exc)))

        for raw, reason in rejected:
            Actor.log.warning("skipping %r: %s", raw, reason)
            await Actor.push_data(
                diagnostic_record(raw, marketplace, "INVALID_TARGET", reason)
            )

        if not targets:
            Actor.log.error("no usable search terms or URLs in input")
            return

        try:
            proxy_configuration = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001 -- proxy is optional locally
            Actor.log.warning("could not create proxy configuration: %s", exc)
            proxy_configuration = None

        proxy_url = await proxy_configuration.new_url() if proxy_configuration else None
        new_proxy_url = proxy_configuration.new_url if proxy_configuration else None
        if not proxy_url:
            Actor.log.warning(
                "running without a proxy -- Amazon blocks repeated search fetches "
                "from one IP; residential proxy is recommended"
            )

        client = AmazonClient(
            marketplace=marketplace, proxy_url=proxy_url, new_proxy_url=new_proxy_url
        )
        stats = {"terms": 0, "pages": 0, "items": 0, "sponsored": 0, "failed": 0}

        try:
            for target in targets:
                stats["terms"] += 1
                seen_asins = set()
                emitted = 0

                for page in range(1, max_pages + 1):
                    url = paginate(target["url"], page)
                    try:
                        html = await client.get_search(url)
                    except CaptchaError as exc:
                        stats["failed"] += 1
                        Actor.log.warning("%s p%s: %s", target["label"], page, exc)
                        await Actor.push_data(diagnostic_record(
                            target["label"], marketplace, "CAPTCHA", str(exc)))
                        break
                    except BlockedError as exc:
                        stats["failed"] += 1
                        Actor.log.warning("%s p%s: %s", target["label"], page, exc)
                        await Actor.push_data(diagnostic_record(
                            target["label"], marketplace, "BLOCKED", str(exc)))
                        break

                    stats["pages"] += 1
                    context = {
                        "label": target["label"],
                        "url": target["url"],
                        "marketplace": marketplace,
                        "page": page,
                        "offset": emitted,
                    }
                    records = parse_page(html, context)
                    if not include_sponsored:
                        records = [r for r in records if not r["isSponsored"]]

                    new_records = []
                    for record in records:
                        # Amazon repeats some ASINs across pages; a duplicate
                        # would inflate any price-distribution analysis.
                        if record["asin"] in seen_asins:
                            continue
                        seen_asins.add(record["asin"])
                        new_records.append(record)

                    if max_items:
                        room = max_items - emitted
                        new_records = new_records[:max(room, 0)]

                    for record in new_records:
                        record["position"] = emitted + 1
                        emitted += 1
                        stats["items"] += 1
                        if record["isSponsored"]:
                            stats["sponsored"] += 1
                        await Actor.push_data(record)

                    priced = [r["price"] for r in new_records if r["price"] is not None]
                    Actor.log.info(
                        "%s p%s: %s new items (%s priced%s)",
                        target["label"], page, len(new_records), len(priced),
                        f", {min(priced):.2f}-{max(priced):.2f}" if priced else "",
                    )

                    if max_items and emitted >= max_items:
                        break
                    if not has_next_page(html):
                        Actor.log.info("%s: no further pages", target["label"])
                        break
                    if page < max_pages and delay_seconds > 0:
                        await asyncio.sleep(delay_seconds + random.uniform(0, 1.0))

                if delay_seconds > 0 and target is not targets[-1]:
                    await asyncio.sleep(delay_seconds + random.uniform(0, 1.0))
        finally:
            await client.close()

        Actor.log.info(
            "done: %s target(s), %s page(s), %s items (%s sponsored), %s failure(s)",
            stats["terms"], stats["pages"], stats["items"],
            stats["sponsored"], stats["failed"],
        )
