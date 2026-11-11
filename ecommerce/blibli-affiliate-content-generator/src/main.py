"""Blibli Affiliate Link Generator & Content Parser -- Apify Actor entrypoint."""

import asyncio
import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import SORT_OPTIONS
from src.content import InvalidInput, finalize, run_query

logger = logging.getLogger(__name__)

DEFAULT_CAPTION = (
    "{name}\n"
    "Rp{price} (diskon {discount}, dari Rp{listPrice})\n"
    "{rating} bintang - {sold} terjual\n"
    "{description}\n"
    "{link}"
)


def _parse_category(raw: str) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if "/" not in value:
        return value
    segments = [s for s in value.split("?")[0].split("/") if s]
    return segments[-1] if segments else None


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        max_items = actor_input.get("maxItemsPerQuery") or 0
        sort_key = actor_input.get("sortBy", "bestSelling")
        concurrency = max(1, min(int(actor_input.get("maxConcurrency") or 5), 10))

        filters = {
            "sort": SORT_OPTIONS.get(sort_key, "16"),
            "min_rating": actor_input.get("minRating") or 0,
            "min_reviews": actor_input.get("minReviewCount") or 0,
            "min_sold": actor_input.get("minSoldCount") or 0,
            "min_discount": actor_input.get("minDiscountPercent") or 0,
            "official_warranty": bool(actor_input.get("officialWarrantyOnly")),
            "official_store": bool(actor_input.get("officialStoreOnly")),
            "top_rated_seller": bool(actor_input.get("topRatedSellerOnly")),
            "image_size": actor_input.get("imageSize", "full"),
            "campaign": actor_input.get("trackingCampaign") or "",
            "source": actor_input.get("trackingSource") or "",
            "medium": actor_input.get("trackingMedium") or "",
            "generate_share_link": actor_input.get("generateShareLink", True),
            "enrich": bool(actor_input.get("enrichFromProductPage")),
            "caption_template": actor_input.get("captionTemplate", DEFAULT_CAPTION),
        }

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
                "Running without a proxy. Blibli is behind Cloudflare and sustained "
                "requests from one IP draw intermittent 403s -- residential proxy is "
                "recommended for anything beyond a small run."
            )

        client = BlibliClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        semaphore = asyncio.Semaphore(concurrency)
        pushed = 0

        try:
            if sort_key not in SORT_OPTIONS:
                raise InvalidInput(
                    f"Unknown sortBy {sort_key!r}. Expected one of {list(SORT_OPTIONS)}."
                )
            if filters["image_size"] not in ("full", "medium", "thumbnail"):
                raise InvalidInput(
                    f"Unknown imageSize {filters['image_size']!r}. "
                    "Expected full, medium or thumbnail."
                )

            queries = [
                {"type": "searchTerm", "value": t.strip(), "label": t.strip()}
                for t in actor_input.get("searchTerms") or []
                if str(t).strip()
            ]
            queries += [
                {"type": "category", "value": c, "label": c}
                for c in (_parse_category(x) for x in actor_input.get("categories") or [])
                if c
            ]
            if not queries:
                raise InvalidInput(
                    "Provide at least one entry in `searchTerms` or `categories`."
                )

            Actor.log.info(
                "Sourcing from %d query/queries, sort=%s, shareLinks=%s, enrich=%s",
                len(queries), sort_key, filters["generate_share_link"], filters["enrich"],
            )

            for query in queries:
                batch = []
                async for record in run_query(client, query, filters, max_items):
                    batch.append(record)
                    # Finalizing (share-link minting, optional page enrichment)
                    # is network-bound and independent per product, so it runs
                    # concurrently in small batches rather than one at a time.
                    if len(batch) >= concurrency * 2:
                        for done in await asyncio.gather(
                            *(finalize(client, r, filters, semaphore) for r in batch)
                        ):
                            await Actor.push_data(done)
                            pushed += 1
                        batch = []
                if batch:
                    for done in await asyncio.gather(
                        *(finalize(client, r, filters, semaphore) for r in batch)
                    ):
                        await Actor.push_data(done)
                        pushed += 1
                Actor.log.info("%s=%r done (%d total)", query["type"], query["value"], pushed)

        except (InvalidInput, BlockedError, UpstreamShapeError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": "none",
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": "none", "_error": "EMPTY_RESULT",
                "_errorDetail": (
                    "No product matched. Loosen minRating / minSoldCount / "
                    "minDiscountPercent, or turn off officialWarrantyOnly."
                ),
            })

        Actor.log.info("Done -- %d record(s) pushed.", pushed)
        await Actor.set_status_message(f"{pushed} product(s)")
