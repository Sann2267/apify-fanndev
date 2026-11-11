"""99.co scraper - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import NinetyNineClient
from .constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    ID_MAX_PAGE,
)
from .modes import MODE_REQUIRED_INPUT, MODES
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("ninetynine")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator needs -- which page hit the challenge wall, when a TLS profile
    rotated, how much of a result set the ceiling left behind -- never appear.
    """
    actor_log = logging.getLogger("ninetynine")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    99.co is behind Cloudflare and escalates to a managed challenge on some
    paths, so residential is the sensible choice for volume. It is still
    optional: recon from a single residential address reached every open
    surface without one. If setup fails -- which is what a local run gets on a
    plan without the Proxy external access feature -- the run continues direct
    and says so, rather than failing outright.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy; expect a higher challenge rate at "
            "volume, and note that any exit-country you asked for is not in "
            "effect.",
            type(exc).__name__, exc,
        )
        return None
    if proxy_configuration is None:
        log.warning("Proxy was requested but no configuration came back; going direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info("Using Apify Proxy (groups=%s)", cfg.get("apifyProxyGroups") or "auto")
    return url


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "idSearch"
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(sorted(MODES))}"
            )

        required = MODE_REQUIRED_INPUT.get(mode)
        if required and not actor_input.get(required):
            # Fail loud: a run with nothing to do should say so rather than
            # finishing green on an empty dataset.
            raise input_error(f"Mode {mode!r} requires a non-empty {required!r} input.")

        log.info("99.co scraper starting | mode=%s", mode)
        if mode == "idSearch":
            log.info(
                "Indonesian search is challenge-gated from page %d, so one "
                "query reaches about %d listings. Use idLocations to split a "
                "broad query into slices that each fit under that ceiling.",
                ID_MAX_PAGE + 1, ID_MAX_PAGE * 20,
            )

        proxy_url = await _proxy_url(actor_input)
        client = NinetyNineClient(
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(
                actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS
            ),
            request_delay=float(
                actor_input.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS)
            ),
        )

        batch: list[dict[str, Any]] = []
        pushed = 0
        errors = 0

        async def flush() -> None:
            nonlocal batch, pushed
            if batch:
                await Actor.push_data(batch)
                pushed += len(batch)
                log.info("Pushed %d records (%d total)", len(batch), pushed)
                batch = []

        try:
            async for record in MODES[mode](client, actor_input):
                if record.get("_error"):
                    errors += 1
                    log.warning(
                        "%s [%s]: %s",
                        record.get("_error"),
                        record.get("_input"),
                        record.get("_errorDetail", ""),
                    )
                batch.append(record)
                if len(batch) >= PUSH_BATCH:
                    await flush()
            await flush()
        except Exception as exc:  # noqa: BLE001 - the run must still leave a trace
            await flush()
            log.exception("Mode %s failed", mode)
            await Actor.push_data(
                error_record(f"mode:{mode}", "run_failed", f"{type(exc).__name__}: {exc}")
            )
            pushed += 1
            raise
        finally:
            client.close()

        if pushed == 0:
            # Never finish with an empty dataset -- downstream joins read that
            # as a crash.
            await Actor.push_data(
                error_record(
                    f"mode:{mode}", "no_results",
                    f"Mode {mode} produced no records for the given input.",
                )
            )
            pushed = 1

        log.info("Done. %d records pushed (%d diagnostic error rows).", pushed, errors)
