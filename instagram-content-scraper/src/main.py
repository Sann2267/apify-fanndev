"""Instagram Public Content Scraper -- Apify Actor entrypoint.

One actor, five modes, one transport. Every mode warms an Instagram entity page,
harvests the persisted-query id Instagram itself ships inline, and replays it
against `/api/graphql/` for pagination. See `constants.py` for why the legacy
`/api/v1/` REST API is not used at all.
"""

from __future__ import annotations

import asyncio
import logging

from apify import Actor

from src.client import BlockedError, InstagramClient, NotFoundError
from src.constants import (
    ALL_MODES,
    DEFAULT_DELAY_SECONDS,
    ERR_BLOCKED,
    ERR_INVALID_INPUT,
    ERR_NOT_FOUND,
    ERR_SHAPE,
    MODE_LOCATION,
    MODE_POST_DETAIL,
    MODE_PROFILE,
)
from src.extract import InvalidInput, parse_location_id, parse_shortcode, parse_username
from src.modes import SCRAPERS, envelope
from src.relay import RelayShapeError
from src.input_errors import input_error

logger = logging.getLogger(__name__)


def resolve_targets(mode: str, raw_entries: list) -> tuple[list[str], list[tuple[str, str]]]:
    """Parse raw input entries into targets, keeping the rejects for reporting."""
    parser = {
        MODE_POST_DETAIL: parse_shortcode,
        MODE_LOCATION: parse_location_id,
    }.get(mode, parse_username)

    targets: list[str] = []
    rejected: list[tuple[str, str]] = []
    for entry in raw_entries:
        text = entry if isinstance(entry, str) else str(entry or "")
        try:
            target = parser(text)
        except InvalidInput as exc:
            rejected.append((text, str(exc)))
            continue
        if target not in targets:
            targets.append(target)
    return targets, rejected


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        mode = (actor_input.get("mode") or MODE_PROFILE).strip().lower()
        raw_entries = actor_input.get("targets") or []
        delay = actor_input.get("delaySeconds")
        delay = DEFAULT_DELAY_SECONDS if delay is None else float(delay)
        options = {
            "maxItems": actor_input.get("maxItemsPerTarget") or 60,
            "includeComments": actor_input.get("includeComments", True),
            "locationTab": actor_input.get("locationTab") or "recent",
        }

        if mode not in ALL_MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Supported modes: {', '.join(ALL_MODES)}."
            )
        if not raw_entries:
            raise input_error(
                "`targets` is empty. Provide usernames for the profile/posts/reels "
                "modes, post URLs or shortcodes for post_detail, or location ids "
                "for location."
            )

        proxy_config = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001 - proxy is recommended, not required
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)

        proxy_url = await proxy_config.new_url() if proxy_config else None
        if not proxy_url:
            Actor.log.warning(
                "Running without a proxy. Instagram throttles anonymous traffic per "
                "IP and answers with a login wall rather than a 429, so residential "
                "proxy is strongly recommended for more than a handful of targets."
            )

        targets, rejected = resolve_targets(mode, raw_entries)
        scrape = SCRAPERS[mode]
        client = InstagramClient(
            proxy_url=proxy_url,
            new_proxy_url=proxy_config.new_url if proxy_config else None,
        )

        pushed = 0
        failed = 0
        try:
            for text, reason in rejected:
                await Actor.push_data(envelope(
                    mode, text, "none", _error=ERR_INVALID_INPUT, _errorDetail=reason
                ))
                pushed += 1
                failed += 1
                Actor.log.warning("Rejected input %r: %s", text, reason)

            for index, target in enumerate(targets, start=1):
                Actor.log.info("[%d/%d] %s: %s", index, len(targets), mode, target)
                try:
                    rows = await scrape(client, target, options)
                except NotFoundError as exc:
                    rows = [envelope(mode, target, "none",
                                     _error=ERR_NOT_FOUND, _errorDetail=str(exc))]
                    failed += 1
                except BlockedError as exc:
                    rows = [envelope(mode, target, "none",
                                     _error=ERR_BLOCKED, _errorDetail=str(exc))]
                    failed += 1
                except RelayShapeError as exc:
                    # Loud on purpose: a shape change means Instagram moved the
                    # payload and the parser needs updating, not that the target
                    # has no data.
                    Actor.log.error("Upstream shape changed for %s: %s", target, exc)
                    rows = [envelope(mode, target, "none",
                                     _error=ERR_SHAPE, _errorDetail=str(exc))]
                    failed += 1
                except Exception as exc:  # noqa: BLE001 - one target must not sink the run
                    Actor.log.exception("Unhandled error for %s", target)
                    rows = [envelope(mode, target, "none",
                                     _error=ERR_SHAPE,
                                     _errorDetail=f"{type(exc).__name__}: {exc}")]
                    failed += 1

                for row in rows:
                    await Actor.push_data(row)
                pushed += len(rows)
                Actor.log.info("  -> %d row(s)", len(rows))

                if delay > 0 and index < len(targets):
                    await asyncio.sleep(delay)
        finally:
            await client.close()

        Actor.log.info(
            "Done. mode=%s targets=%d rows=%d failed_targets=%d",
            mode, len(targets), pushed, failed,
        )
        if pushed and failed == len(targets) + len(rejected) and targets:
            # Every target failed -- surface it as a failed run rather than an
            # empty-looking success.
            raise RuntimeError(
                f"All {len(targets)} target(s) failed; see the diagnostic rows in "
                "the dataset for per-target detail."
            )
