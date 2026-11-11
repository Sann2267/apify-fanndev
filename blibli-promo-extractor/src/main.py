"""Blibli Flash Sale / Promo Extractor -- Apify Actor entrypoint."""

import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import FLASH_SALE_SORTS, PROMOTION_SORTS, SEARCH_SORTS
from src.modes import (
    fetch_schedules,
    run_discounted_products,
    run_flash_sale,
    run_promo_campaigns,
)

logger = logging.getLogger(__name__)

VALID_MODES = ("flashSale", "promoCampaigns", "discountedProducts")


def _parse_category(raw: str) -> str | None:
    """Accept a bare category code (`FA-1000099`, `53400`) or a full Blibli
    category URL (`https://www.blibli.com/c3/memory-card/ME-1000006`)."""
    value = str(raw or "").strip()
    if not value:
        return None
    if "/" not in value:
        return value
    segments = [s for s in value.split("?")[0].split("/") if s]
    return segments[-1] if segments else None


def _select_schedules(schedules: list[dict], scope: str) -> list[dict]:
    """`current` keeps only the session that is live now; `all` keeps every
    window the endpoint advertises (typically today's plus tomorrow's)."""
    if scope != "current" or not schedules:
        return schedules
    import time

    now_ms = int(time.time() * 1000)
    live = [s for s in schedules if s.get("start", 0) <= now_ms <= s.get("end", 0)]
    # If nothing is live (between sessions), fall back to the earliest
    # upcoming window rather than emitting nothing at all.
    return live or schedules[:1]


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode", "flashSale")
        max_items = actor_input.get("maxItems") or 0
        min_discount = actor_input.get("minDiscountPercent") or 0

        # Proxy setup is best-effort: outside the platform (local runs, no
        # APIFY_TOKEN) there is no proxy password, and a direct connection
        # still works fine against Blibli. Degrade instead of dying.
        proxy_config = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)

        proxy_url = await proxy_config.new_url() if proxy_config else None
        new_proxy_url = proxy_config.new_url if proxy_config else None
        if proxy_url:
            Actor.log.info("Using Apify Proxy (residential recommended, country ID).")
        else:
            Actor.log.warning(
                "Running without a proxy. Blibli is behind Cloudflare -- a datacenter "
                "or shared IP may be rate-limited on long runs."
            )

        client = BlibliClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        pushed = 0

        try:
            # Validated inside the try so a bad mode still produces a
            # diagnostic row rather than an empty dataset.
            if mode not in VALID_MODES:
                raise ValueError(f"Unknown mode {mode!r}. Expected one of {VALID_MODES}.")

            if mode == "flashSale":
                scope = actor_input.get("scheduleScope", "current")
                schedules = _select_schedules(await fetch_schedules(client), scope)
                Actor.log.info(
                    "Flash sale: %d schedule(s) selected (%s) -> %s",
                    len(schedules), scope, [s.get("id") for s in schedules],
                )
                categories = [
                    c for c in (_parse_category(x) for x in actor_input.get("categories") or []) if c
                ]
                sort = actor_input.get("flashSaleSort", "biggestDiscount")
                if sort not in FLASH_SALE_SORTS:
                    raise ValueError(
                        f"Unknown flashSaleSort {sort!r}. Expected one of {list(FLASH_SALE_SORTS)}."
                    )
                stream = run_flash_sale(
                    client, schedules, categories, sort, min_discount, max_items
                )

            elif mode == "promoCampaigns":
                sort = actor_input.get("promoSort", "ending_soon")
                if sort not in PROMOTION_SORTS:
                    raise ValueError(
                        f"Unknown promoSort {sort!r}. Expected one of {list(PROMOTION_SORTS)}."
                    )
                stream = run_promo_campaigns(client, sort, max_items)

            else:  # discountedProducts
                queries = [
                    {"type": "searchTerm", "value": term.strip(), "label": term.strip()}
                    for term in actor_input.get("searchTerms") or []
                    if str(term).strip()
                ]
                queries += [
                    {"type": "category", "value": code, "label": code}
                    for code in (
                        _parse_category(x) for x in actor_input.get("categories") or []
                    )
                    if code
                ]
                if not queries:
                    raise ValueError(
                        "Mode 'discountedProducts' needs at least one entry in "
                        "`searchTerms` or `categories`."
                    )
                sort = actor_input.get("searchSort", "relevance")
                if sort not in SEARCH_SORTS:
                    raise ValueError(
                        f"Unknown searchSort {sort!r}. Expected one of {list(SEARCH_SORTS)}."
                    )
                Actor.log.info("Discounted products: %d query/queries.", len(queries))
                stream = run_discounted_products(
                    client,
                    queries,
                    min_discount,
                    actor_input.get("promoFilter") or None,
                    sort,
                    max_items,
                )

            async for record in stream:
                await Actor.push_data(record)
                pushed += 1

        except (BlockedError, UpstreamShapeError, ValueError) as exc:
            # Emit a diagnostic row instead of failing silently -- downstream
            # joins must always see a row explaining an empty run.
            error_kind = {
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
                ValueError: "INVALID_INPUT",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data(
                {"_input": mode, "_source": "none", "_error": error_kind, "_errorDetail": str(exc)}
            )
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            # A genuinely empty result is legitimate (e.g. a 90% discount
            # threshold matching nothing), but it must be visible.
            Actor.log.warning("Run produced no records.")
            await Actor.push_data(
                {
                    "_input": mode,
                    "_source": "none",
                    "_error": "EMPTY_RESULT",
                    "_errorDetail": (
                        "No item matched. Loosen minDiscountPercent, widen categories/"
                        "searchTerms, or set scheduleScope to 'all'."
                    ),
                }
            )

        Actor.log.info("Done -- mode=%s, %d record(s) pushed.", mode, pushed)
        await Actor.set_status_message(f"{mode}: {pushed} record(s)")
