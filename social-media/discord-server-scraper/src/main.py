"""Discord Server & Community Scraper - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import DiscordClient
from .constants import (
    API_REQUEST_DELAY_SECS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    DISCOVERY_PAGE_SIZE,
)
from .modes import MODE_REQUIRED_INPUT, MODES, Budget, as_strings
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("discord")

PUSH_BATCH = 100

# Which input arrays each mode reads, so a run can be given one list and the
# actor puts it where the chosen mode looks for it.
TARGET_KEYS = (
    "searchKeywords",
    "categories",
    "serverTargets",
    "inviteCodes",
    "gameTargets",
    "applicationIds",
)


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator needs -- which server had its widget switched off, when a rate
    limit forced a pause, how much of the item budget is left -- never appear.
    """
    actor_log = logging.getLogger("discord")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    Discord served every surface in this actor to a plain datacentre address
    during recon, so proxying is genuinely optional here -- unlike the Google
    and Etsy actors in this portfolio, where it decides whether the run works
    at all. What a proxy buys on Discord is rate-limit headroom: the directory
    listing allows about six requests back to back per address, so a long
    Discovery walk finishes sooner behind rotating addresses.

    Setup failures never fail the run. A local run on a plan without the Proxy
    external-access feature continues direct and says so.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy. Discord serves every surface this "
            "actor uses to an unproxied address, so the run should still "
            "work; only rate-limit headroom is lost.",
            type(exc).__name__, exc,
        )
        return None
    if proxy_configuration is None:
        log.warning("Proxy was requested but no configuration came back; going direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info("Using Apify Proxy (groups=%s)", cfg.get("apifyProxyGroups") or "auto")
    return url


def _collect_inputs(actor_input: dict[str, Any], mode: str) -> dict[str, Any]:
    """Normalise every input array, and accept a single generic list.

    Modes read differently named arrays, but a buyer chaining this actor from
    another one usually has exactly one list. `targets` is accepted as an alias
    for whichever array the chosen mode needs, so the actor can be driven with
    one field regardless of mode.
    """
    options: dict[str, Any] = dict(actor_input)
    for key in TARGET_KEYS:
        options[key] = as_strings(actor_input.get(key))

    generic = as_strings(actor_input.get("targets"))
    if generic:
        required = MODE_REQUIRED_INPUT.get(mode, ())
        if required and not options.get(required[0]):
            options[required[0]] = generic
            log.info(
                "Routed %d value(s) from 'targets' into '%s' for mode %s.",
                len(generic), required[0], mode,
            )
    return options


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "discoverySearch"
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(MODES)}"
            )

        options = _collect_inputs(actor_input, mode)

        required = MODE_REQUIRED_INPUT.get(mode, ())
        if required and not any(options.get(key) for key in required):
            # Fail loud: a run with nothing to do should say so rather than
            # finishing green on an empty dataset.
            raise input_error(
                f"Mode {mode!r} needs at least one of: {', '.join(required)}."
            )

        max_items = int(actor_input.get("maxItems") or 0)
        log.info(
            "Discord Server & Community Scraper | mode=%s maxItems=%s",
            mode, max_items or "unlimited",
        )
        if mode in ("discoverySearch", "discoveryCategory"):
            pages = int(actor_input.get("maxPagesPerTarget") or 5)
            log.info(
                "Discovery serves %d servers per request and ignores any page "
                "size you send, so maxPagesPerTarget=%d is up to %d servers "
                "per keyword or category.",
                DISCOVERY_PAGE_SIZE, pages, pages * DISCOVERY_PAGE_SIZE,
            )

        proxy_url = await _proxy_url(actor_input)
        client = DiscordClient(
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(
                actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS
            ),
            request_delay=float(
                actor_input.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS)
            ),
            api_request_delay=float(
                actor_input.get("apiRequestDelaySecs", API_REQUEST_DELAY_SECS)
            ),
        )
        budget = Budget(max_items)

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
            async for rec in MODES[mode](client, options, budget):
                if rec.get("item_type") == "error":
                    errors += 1
                    data = rec.get("data") or {}
                    log.warning(
                        "%s [%s]: %s",
                        data.get("_error"), data.get("_input"),
                        data.get("_errorDetail", ""),
                    )
                batch.append(rec)
                if len(batch) >= PUSH_BATCH:
                    await flush()
            await flush()
        except Exception as exc:  # noqa: BLE001 - the run must still leave a trace
            await flush()
            log.exception("Mode %s failed", mode)
            await Actor.push_data(
                error_record(
                    f"mode:{mode}", "run_failed",
                    f"{type(exc).__name__}: {exc}", mode=mode,
                )
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
                    mode=mode,
                )
            )
            pushed = 1

        rate_note = (
            f" {client.rate_limited_count} request(s) were rate limited and "
            "retried after a pause; raise requestDelaySecs if that number is "
            "large."
            if client.rate_limited_count else ""
        )
        log.info(
            "Done. %d records pushed (%d diagnostic error rows) from %d HTTP "
            "requests.%s",
            pushed, errors, client.request_count, rate_note,
        )
