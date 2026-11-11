"""TikTok All-in-One Scraper -- Apify Actor entrypoint.

One actor, five modes, one transport: TikTok's public embed widget pages plus its
official oEmbed endpoint. See `constants.py` for the recon that explains why the
consumer web app, its signed JSON APIs and the Creative Center are all untouched
here, and what the resulting ceilings are.
"""

from __future__ import annotations

import asyncio
import logging

from apify import Actor

from src.client import BlockedError, NotFoundError, TikTokClient
from src.constants import (
    ALL_MODES,
    DEFAULT_DELAY_SECONDS,
    ERR_BLOCKED,
    ERR_INVALID_INPUT,
    ERR_NOT_FOUND,
    ERR_SHAPE,
    MODE_HASHTAG,
    MODE_MUSIC,
    MODE_OEMBED,
    MODE_PROFILE,
    MODE_VIDEO,
    SOURCE_NONE,
)
from src.extract import (
    InvalidInput,
    parse_hashtag,
    parse_music_id,
    parse_username,
    parse_video_id,
    parse_video_url,
)
from src.modes import SCRAPERS, envelope
from src.state import ShapeError
from src.input_errors import input_error

logger = logging.getLogger(__name__)

PARSERS = {
    MODE_PROFILE: parse_username,
    MODE_VIDEO: parse_video_id,
    MODE_HASHTAG: parse_hashtag,
    MODE_MUSIC: parse_music_id,
    MODE_OEMBED: parse_video_url,
}

EMPTY_TARGETS_HELP = (
    "`targets` is empty. Provide usernames or profile urls for the profile mode, "
    "video urls / short links / numeric ids for video, hashtags for hashtag, "
    "music urls or music ids for music, and full video urls for oembed."
)


def resolve_targets(mode: str, raw_entries: list) -> tuple[list[str], list[tuple[str, str]]]:
    """Parse raw input entries into targets, keeping the rejects for reporting."""
    parser = PARSERS[mode]
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
        options = {"maxItems": actor_input.get("maxItemsPerTarget") or 0}

        if mode not in ALL_MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Supported modes: {', '.join(ALL_MODES)}."
            )
        if not raw_entries:
            raise input_error(EMPTY_TARGETS_HELP)

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
                "Running without a proxy. TikTok answers repeated embed requests "
                "from one IP with HTTP 503 after a handful of calls, so a proxy is "
                "strongly recommended for more than a few targets."
            )

        targets, rejected = resolve_targets(mode, raw_entries)
        scrape = SCRAPERS[mode]
        client = TikTokClient(
            proxy_url=proxy_url,
            new_proxy_url=proxy_config.new_url if proxy_config else None,
        )

        pushed = 0
        failed = 0
        try:
            for text, reason in rejected:
                await Actor.push_data(envelope(
                    mode, text, SOURCE_NONE,
                    _error=ERR_INVALID_INPUT, _errorDetail=reason,
                ))
                pushed += 1
                failed += 1
                Actor.log.warning("Rejected input %r: %s", text, reason)

            for index, target in enumerate(targets, start=1):
                Actor.log.info("[%d/%d] %s: %s", index, len(targets), mode, target)
                try:
                    rows = await scrape(client, target, options)
                except NotFoundError as exc:
                    rows = [envelope(mode, target, SOURCE_NONE,
                                     _error=ERR_NOT_FOUND, _errorDetail=str(exc))]
                    failed += 1
                except BlockedError as exc:
                    rows = [envelope(mode, target, SOURCE_NONE,
                                     _error=ERR_BLOCKED, _errorDetail=str(exc))]
                    failed += 1
                except ShapeError as exc:
                    # Loud on purpose: a shape change means TikTok moved the
                    # payload and the parser needs updating, not that the target
                    # has no data.
                    Actor.log.error("Upstream shape changed for %s: %s", target, exc)
                    rows = [envelope(mode, target, SOURCE_NONE,
                                     _error=ERR_SHAPE, _errorDetail=str(exc))]
                    failed += 1
                except Exception as exc:  # noqa: BLE001 - one target must not sink the run
                    Actor.log.exception("Unhandled error for %s", target)
                    rows = [envelope(mode, target, SOURCE_NONE,
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
        if targets and failed >= len(targets) + len(rejected):
            # Every target failed -- surface it as a failed run rather than an
            # empty-looking success.
            raise RuntimeError(
                f"All {len(targets)} target(s) failed; see the diagnostic rows in "
                "the dataset for per-target detail."
            )
