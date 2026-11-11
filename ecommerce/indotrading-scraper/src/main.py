"""Indotrading.com scraper - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import IndotradingClient
from .constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECS,
    PRODUCTS_PER_PAGE,
)
from .modes import MODE_REQUIRED_INPUT, MODES
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("indotrading")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator actually needs -- which page a category ran dry on, when a TLS
    profile rotated, how many contact lookups degraded -- never appear.
    """
    actor_log = logging.getLogger("indotrading")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    Recon found no IP gate: 25 sequential requests in 9.2 seconds from one
    datacenter address all returned 200 with full product payloads, and the
    only Cloudflare rule in play keys on the TLS fingerprint. So the default
    is no proxy. Residential stays available for volume runs and for anyone
    who wants an Indonesian exit address.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxying is optional for this target
        # Typically "Proxy external access isn't enabled for your account",
        # which is what a local run on a plan without that feature gets. Since
        # indotrading has no IP gate, going direct still returns full data --
        # so degrade loudly rather than failing a run that would have worked.
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy. Indotrading has no IP-based gate, so "
            "this run should still return complete data; if you needed a "
            "specific exit country, the results will be from this machine's "
            "address instead.",
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

        mode = actor_input.get("mode") or "categoryProducts"
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(sorted(MODES))}"
            )

        required = MODE_REQUIRED_INPUT.get(mode)
        if required and not actor_input.get(required):
            # Fail loud: a run with nothing to do should say so rather than
            # finishing green on an empty dataset.
            raise input_error(f"Mode {mode!r} requires a non-empty {required!r} input.")

        log.info(
            "Indotrading scraper starting | mode=%s (listings return %d products "
            "per page; the site's own page counter overstates how far it can "
            "actually be paged, so paging stops on the first empty page)",
            mode, PRODUCTS_PER_PAGE,
        )
        if actor_input.get("includeContact"):
            log.info(
                "includeContact is on: one extra request per product to fetch the "
                "supplier WhatsApp number."
            )

        proxy_url = await _proxy_url(actor_input)
        client = IndotradingClient(
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(
                actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS
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
                    # Error rows land in the dataset, but an operator reads the
                    # run log first, so say it in both places.
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
            # as a crash. Leave a row saying the input was valid but empty.
            await Actor.push_data(
                error_record(
                    f"mode:{mode}",
                    "no_results",
                    f"Mode {mode} produced no records for the given input.",
                )
            )
            pushed = 1

        log.info("Done. %d records pushed (%d diagnostic error rows).", pushed, errors)
