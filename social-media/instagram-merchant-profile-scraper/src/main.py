"""Instagram Merchant Profile & Bio-Link Extractor -- Apify Actor entrypoint."""

import asyncio
import logging

from apify import Actor

from src.client import BlockedError, InstagramClient, NotFound, UpstreamShapeError
from src.constants import DEFAULT_DELAY_SECONDS, SOURCE_NONE
from src.profile import (
    InvalidInput,
    enrich,
    from_api,
    from_html,
    from_meta,
    resolve_username,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_targets = actor_input.get("usernames") or []
        include_posts = actor_input.get("includeRecentPosts", True)
        max_posts = actor_input.get("maxPostsPerProfile") or 12
        delay = actor_input.get("delaySeconds")
        delay = DEFAULT_DELAY_SECONDS if delay is None else float(delay)

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
                "Running without a proxy. Instagram rate-limits anonymous traffic hard "
                "and will start serving login walls after a handful of profiles -- "
                "residential proxy is strongly recommended."
            )

        client = InstagramClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        pushed = 0
        stats = {"api": 0, "html": 0, "meta": 0, "failed": 0}

        try:
            if not raw_targets:
                raise InvalidInput(
                    "`usernames` is empty. Provide Instagram handles or profile URLs, "
                    'e.g. ["cottonink", "https://www.instagram.com/nike/"].'
                )

            usernames: list[str] = []
            for raw in raw_targets:
                try:
                    username = resolve_username(raw)
                except InvalidInput as exc:
                    Actor.log.error("Skipping %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": SOURCE_NONE,
                        "_error": "INVALID_INPUT", "_errorDetail": str(exc),
                    })
                    pushed += 1
                    stats["failed"] += 1
                else:
                    if username not in usernames:
                        usernames.append(username)
            if not usernames:
                raise InvalidInput("No usable usernames among the provided inputs.")

            Actor.log.info("Scraping %d profile(s)", len(usernames))

            for index, username in enumerate(usernames):
                try:
                    # The warm-up doubles as strategy S2's data source, so
                    # nothing is wasted even when the API succeeds.
                    page_html = await client.warm_profile(username)

                    record = None
                    user = await client.profile_api(username)
                    if user:
                        record = from_api(username, user, max_posts if include_posts else 0)
                        stats["api"] += 1
                    else:
                        # The API intermittently returns nothing for accounts
                        # whose page loads fine; fall back rather than fail.
                        Actor.log.info(
                            "@%s: API returned no user, falling back to page HTML", username
                        )
                        record = from_html(username, page_html)
                        if record:
                            stats["html"] += 1
                        else:
                            record = from_meta(username, page_html)
                            if record:
                                stats["meta"] += 1

                    if not record:
                        raise UpstreamShapeError(
                            f"@{username} returned a page but no strategy could parse a "
                            "profile from it -- Instagram's markup may have changed."
                        )

                    if not include_posts:
                        record["recentPosts"] = []
                    await Actor.push_data(enrich(record))
                    pushed += 1
                    Actor.log.info(
                        "@%s via %s | %s followers | %d bio link(s) %s",
                        username, record["_source"], record.get("followers"),
                        len(record.get("bioLinks") or []),
                        record.get("marketplaces") or "",
                    )

                except (NotFound, BlockedError, UpstreamShapeError) as exc:
                    stats["failed"] += 1
                    error_kind = {
                        NotFound: "NOT_FOUND",
                        BlockedError: "BLOCKED_AFTER_RETRIES",
                        UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
                    }[type(exc)]
                    Actor.log.error("@%s failed: %s", username, exc)
                    await Actor.push_data({
                        "_input": username, "_source": SOURCE_NONE,
                        "username": username,
                        "_error": error_kind, "_errorDetail": str(exc),
                    })
                    pushed += 1

                # Pacing matters more than concurrency here: Instagram's
                # anonymous throttle is per-IP and unforgiving, so profiles
                # are fetched sequentially with a gap.
                if delay and index < len(usernames) - 1:
                    await asyncio.sleep(delay)

        except (InvalidInput, BlockedError, UpstreamShapeError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": SOURCE_NONE,
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": SOURCE_NONE, "_error": "EMPTY_RESULT",
                "_errorDetail": "No profile resolved. Check the usernames supplied.",
            })

        Actor.log.info(
            "Done -- %d pushed | %d via API, %d via HTML, %d via og-meta, %d failed",
            pushed, stats["api"], stats["html"], stats["meta"], stats["failed"],
        )
        await Actor.set_status_message(
            f"{stats['api'] + stats['html'] + stats['meta']} profile(s), "
            f"{stats['failed']} failed"
        )
