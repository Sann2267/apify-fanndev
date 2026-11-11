"""Blibli Homepage Recommendation & Ad Placement Tracker -- Apify Actor entrypoint."""

import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import DEFAULT_MAX_PAGES_PER_TAB
from src.feed import fetch_tabs, run_feed

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        requested_tabs = [str(t).strip() for t in (actor_input.get("tabs") or []) if str(t).strip()]
        max_pages_per_tab = actor_input.get("maxPagesPerTab")
        max_pages_per_tab = int(max_pages_per_tab) if max_pages_per_tab else DEFAULT_MAX_PAGES_PER_TAB
        max_items_per_tab = int(actor_input.get("maxItemsPerTab") or 0)
        include_ad_banners = actor_input.get("includeAdBanners", True)

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
        input_label = ", ".join(requested_tabs) if requested_tabs else "all tabs"

        try:
            all_tabs = await fetch_tabs(client)
            Actor.log.info(
                "Discovered %d homepage tab(s): %s",
                len(all_tabs), [t.get("name") for t in all_tabs],
            )

            if requested_tabs:
                by_name = {t.get("name"): t for t in all_tabs}
                tabs = []
                for name in requested_tabs:
                    if name in by_name:
                        tabs.append(by_name[name])
                    else:
                        Actor.log.warning(
                            "Requested tab %r not found in live tab list -- skipping.", name
                        )
                if not tabs:
                    raise ValueError(
                        f"None of the requested tabs {requested_tabs} matched a live tab. "
                        f"Currently available: {[t.get('name') for t in all_tabs]}"
                    )
            else:
                tabs = all_tabs

            stream = run_feed(client, tabs, max_pages_per_tab, max_items_per_tab, include_ad_banners)
            async for record in stream:
                await Actor.push_data(record)
                pushed += 1

        except (BlockedError, UpstreamShapeError, ValueError) as exc:
            error_kind = {
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
                ValueError: "INVALID_INPUT",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data(
                {"_input": input_label, "_source": "none", "_error": error_kind, "_errorDetail": str(exc)}
            )
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data(
                {
                    "_input": input_label,
                    "_source": "none",
                    "_error": "EMPTY_RESULT",
                    "_errorDetail": "No tiles matched. Try a different tab or check includeAdBanners.",
                }
            )

        Actor.log.info("Done -- %d record(s) pushed across %s.", pushed, input_label)
        await Actor.set_status_message(f"{pushed} record(s) pushed")
