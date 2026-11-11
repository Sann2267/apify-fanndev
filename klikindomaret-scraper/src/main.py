"""klikindomaret.com (Indomaret Xpress) scraper -- Apify Actor entrypoint.

Single actor, mode-selected. Shared session bootstrap (store resolution + WAF
tokens) is why these live in one actor rather than five: every mode pays the
same AWS-WAF / Cloudflare setup, so splitting would duplicate it.
"""

from __future__ import annotations

import logging

from apify import Actor

from src.client import BlockedError, KlikClient, UpstreamShapeError
from src.constants import DEFAULT_SEARCH_TERM
from src.modes import (
    resolve_store,
    run_category_tree,
    run_product_search,
    run_promo_banners,
    run_stores,
    run_suggestions,
)
from src.waf import WafError, WafManager

logger = logging.getLogger(__name__)

VALID_MODES = ("productSearch", "categoryTree", "promoBanners", "searchSuggestions", "stores")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode", "productSearch")
        max_items = actor_input.get("maxItems") or 0
        store_code = (actor_input.get("storeCode") or "").strip() or None
        district_id = (actor_input.get("districtId") or "").strip() or None
        latitude = (actor_input.get("latitude") or "").strip() or None
        longitude = (actor_input.get("longitude") or "").strip() or None

        proxy_url = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
            if proxy_config:
                # Sticky session: the Camoufox-earned cf_clearance cookie is
                # IP-bound, so the browser and the curl_cffi crawl must share the
                # same proxy exit IP. A fixed session id pins both to one IP.
                import secrets

                session_id = "klik" + secrets.token_hex(6)
                proxy_url = await proxy_config.new_url(session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)
        if proxy_url:
            Actor.log.info("Using Apify Proxy (residential + country ID recommended).")
        else:
            Actor.log.warning("Running without a proxy -- fine for local tests / short runs.")

        waf = WafManager(proxy_url=proxy_url)
        client = KlikClient(waf, proxy_url=proxy_url)
        pushed = 0

        try:
            if mode not in VALID_MODES:
                raise ValueError(f"Unknown mode {mode!r}. Expected one of {VALID_MODES}.")

            # Mint the AWS token up front (all modes need it).
            await waf.ensure_aws_token()

            if mode == "stores":
                district_ids = [
                    str(d).strip()
                    for d in (actor_input.get("districtIds") or ([district_id] if district_id else []))
                    if str(d).strip()
                ]
                stream = run_stores(client, district_ids)
            else:
                store = await resolve_store(client, store_code, district_id, latitude, longitude)
                Actor.log.info("Store context: %r", store)

                if mode == "categoryTree":
                    stream = run_category_tree(client, store)
                elif mode == "searchSuggestions":
                    stream = run_suggestions(client, store)
                elif mode == "promoBanners":
                    stream = run_promo_banners(client, store, max_items)
                else:  # productSearch
                    queries = [
                        {"type": "keyword", "value": t.strip(), "label": t.strip()}
                        for t in (actor_input.get("searchTerms") or [])
                        if str(t).strip()
                    ]
                    queries += [
                        {"type": "category", "value": str(c).strip(), "label": f"category:{c}"}
                        for c in (actor_input.get("categoryIds") or [])
                        if str(c).strip()
                    ]
                    if not queries:
                        # An empty productSearch input (the platform default)
                        # used to fail the whole run; scrape a staple keyword
                        # instead so a no-input run still demonstrates output.
                        Actor.log.warning(
                            "No `searchTerms` or `categoryIds` given -- falling back "
                            "to the default keyword %r.",
                            DEFAULT_SEARCH_TERM,
                        )
                        queries = [
                            {
                                "type": "keyword",
                                "value": DEFAULT_SEARCH_TERM,
                                "label": DEFAULT_SEARCH_TERM,
                            }
                        ]
                    Actor.log.info("Product search: %d query/queries.", len(queries))
                    stream = run_product_search(client, store, queries, max_items)

            async for rec in stream:
                await Actor.push_data(rec)
                pushed += 1

        except (BlockedError, UpstreamShapeError, WafError, ValueError) as exc:
            error_kind = {
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
                WafError: "WAF_BOOTSTRAP_FAILED",
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
            Actor.log.warning("Run produced no records.")
            await Actor.push_data(
                {
                    "_input": mode,
                    "_source": "none",
                    "_error": "EMPTY_RESULT",
                    "_errorDetail": "No item matched. Check searchTerms/categoryIds or store context.",
                }
            )

        Actor.log.info("Done -- mode=%s, %d record(s) pushed.", mode, pushed)
        await Actor.set_status_message(f"{mode}: {pushed} record(s)")
