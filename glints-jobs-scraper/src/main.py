"""Glints Jobs Scraper - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import GlintsClient
from .constants import ANON_MAX_PAGE, DEFAULT_COUNTRY, MAX_PAGE_SIZE
from .modes import MODES
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("glints")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK only configures the 'apify' logger, so without this the per-mode
    progress lines -- how many jobs a term returned, when a term hits the
    anonymous page-1 ceiling, which TLS profile a retry rotated to -- never
    reach the run log, which is exactly where they are needed.
    """
    glints_log = logging.getLogger("glints")
    if glints_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    glints_log.addHandler(handler)
    glints_log.setLevel(logging.INFO)
    glints_log.propagate = False


def _needs_targets(mode: str) -> str | None:
    """Which input list a mode cannot run without."""
    if mode in ("jobDetail", "similarJobs"):
        return "jobUrlsOrIds"
    if mode == "company":
        return "companyUrlsOrIds"
    if mode == "suggestions":
        return "searchTerms"
    return None


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    Recon found no IP gate on Glints -- 54 requests in four seconds from a
    single datacenter address all returned 200 -- so the default is no proxy.
    Residential remains available for runs that need a specific market's exit
    country or that hit a future rate limit.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    if proxy_configuration is None:
        log.warning("Proxy was requested but no configuration came back; continuing direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info("Using Apify Proxy (groups=%s)", cfg.get("apifyProxyGroups") or "auto")
    return url


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "search"
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(sorted(MODES))}"
            )

        country = (actor_input.get("countryCode") or DEFAULT_COUNTRY).upper()
        required = _needs_targets(mode)
        if required and not actor_input.get(required):
            # Fail loud: a run with nothing to do should say so, not finish
            # green with an empty dataset.
            raise input_error(f"Mode {mode!r} requires a non-empty {required!r} input.")

        page_size = int(actor_input.get("pageSize") or MAX_PAGE_SIZE)
        if page_size > MAX_PAGE_SIZE:
            log.warning(
                "pageSize %d exceeds the anonymous ceiling; Glints will cap it at %d.",
                page_size, MAX_PAGE_SIZE,
            )

        log.info(
            "Glints scraper starting | mode=%s country=%s (anonymous access: "
            "search reaches page %d, up to %d jobs per query)",
            mode, country, ANON_MAX_PAGE, MAX_PAGE_SIZE,
        )

        proxy_url = await _proxy_url(actor_input)
        client = GlintsClient(
            proxy_url=proxy_url,
            country_code=country,
            max_retries=int(actor_input.get("maxRetries") or 4),
            request_timeout=int(actor_input.get("requestTimeoutSecs") or 45),
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
            # as a crash. Leave a row saying the query was valid but empty.
            await Actor.push_data(
                error_record(
                    f"mode:{mode}",
                    "no_results",
                    f"Mode {mode} produced no records for the given input.",
                )
            )
            pushed = 1

        log.info("Done. %d records pushed (%d diagnostic error rows).", pushed, errors)
