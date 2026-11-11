"""Etsy Ultimate Data Extractor - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import EtsyClient
from .constants import (
    CATEGORY_MAX_PAGE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
)
from .modes import MODE_REQUIRED_INPUT, MODES, Budget, normalise_locale
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("etsy")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator needs -- which URL hit the challenge wall, when a TLS profile
    rotated, how much of the item budget is left -- never appear.
    """
    actor_log = logging.getLogger("etsy")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    Recon found no surface where a datacentre address was served: the
    BUYPROXIES group drew the DataDome interstitial even on the category grid
    that residential and the platform's own address both cleared. So
    RESIDENTIAL is the default here, and a run that asks for datacentre gets a
    warning rather than a silent block wave.

    Proxying stays optional: a single clean residential address reached every
    open surface without one. If setup fails -- which is what a local run gets
    on a plan without the Proxy external access feature -- the run continues
    direct and says so, rather than failing outright.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.warning(
            "Running without Apify Proxy. Etsy scores request rate per address, "
            "and during recon roughly 30 requests were enough to move one "
            "address from served to challenged on every product page. Expect a "
            "short run to work and a long one to degrade."
        )
        return None
    groups = cfg.get("apifyProxyGroups") or []
    if groups and "RESIDENTIAL" not in groups:
        log.warning(
            "Proxy groups %s do not include RESIDENTIAL. Datacentre addresses "
            "were challenged by DataDome on every Etsy surface tested, "
            "including the category grid. Expect this run to fail.", groups,
        )
    try:
        proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy; any exit country you asked for is not "
            "in effect, and prices will follow this machine's address.",
            type(exc).__name__, exc,
        )
        return None
    if proxy_configuration is None:
        log.warning("Proxy was requested but no configuration came back; going direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info("Using Apify Proxy (groups=%s)", groups or "auto")
    return url


def _as_urls(raw: Any) -> list[str]:
    """Accept both shapes Apify's `requestListSources` editor can produce.

    The console emits `[{"url": "..."}]`; a run started from the API or from
    another actor usually sends plain strings. Both are normal, so both work.
    """
    out: list[str] = []
    for entry in raw or []:
        if isinstance(entry, str):
            value = entry.strip()
        elif isinstance(entry, dict):
            value = str(entry.get("url") or "").strip()
        else:
            continue
        if value:
            out.append(value)
    return out


def _warn_about_badges(actor_input: dict[str, Any]) -> None:
    if not actor_input.get("bestsellerOnly"):
        return
    log.warning(
        "bestsellerOnly is on. Etsy currently does NOT render the Bestseller or "
        "Star Seller badge into server-side HTML on grid surfaces -- the page's "
        "own listing-card config reports badges_disabled and the "
        "quality_signals.bestseller_logic_desktop experiment is off -- so this "
        "filter will keep very few rows, and none at all from category or shop "
        "grids. Use minReviewCount and minRating for popularity filtering "
        "instead; they read fields Etsy does render."
    )


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "search"
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(sorted(MODES))}"
            )

        options: dict[str, Any] = dict(actor_input)
        options["startUrls"] = _as_urls(actor_input.get("startUrls"))
        options["productUrls"] = _as_urls(actor_input.get("productUrls"))
        options["locale"] = normalise_locale(actor_input.get("locale"))

        required = MODE_REQUIRED_INPUT.get(mode, ())
        if required and not any(options.get(key) for key in required):
            # Fail loud: a run with nothing to do should say so rather than
            # finishing green on an empty dataset.
            raise input_error(
                f"Mode {mode!r} needs at least one of: {', '.join(required)}."
            )

        log.info(
            "Etsy Ultimate Data Extractor | mode=%s locale=%s maxItems=%s",
            mode, options["locale"] or "(site default, currency follows the exit IP)",
            actor_input.get("maxItems") or "unlimited",
        )
        if mode in ("search", "deepCrawl") and options.get("searchKeywords"):
            log.info(
                "Keyword search runs through /search/shops, the one keyword "
                "surface Etsy's robots.txt allows, and then each matched shop's "
                "own catalogue search. Etsy disallows /search?q= product search "
                "for every crawler, so this actor never requests it."
            )
        _warn_about_badges(actor_input)

        proxy_url = await _proxy_url(actor_input)
        client = EtsyClient(
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(
                actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS
            ),
            request_delay=float(
                actor_input.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS)
            ),
        )
        budget = Budget(int(actor_input.get("maxItems") or 0))

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
                        data.get("_error"), data.get("_input"), data.get("_errorDetail", ""),
                    )
                batch.append(rec)
                if len(batch) >= PUSH_BATCH:
                    await flush()
            await flush()
        except Exception as exc:  # noqa: BLE001 - the run must still leave a trace
            await flush()
            log.exception("Mode %s failed", mode)
            await Actor.push_data(
                error_record(f"mode:{mode}", "run_failed", f"{type(exc).__name__}: {exc}", mode=mode)
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

        blocked_note = (
            f" {client.blocked_count} of {client.request_count} requests drew the "
            f"DataDome interstitial and were retried on another TLS profile."
            if client.blocked_count
            else ""
        )
        log.info(
            "Done. %d records pushed (%d diagnostic error rows).%s",
            pushed, errors, blocked_note,
        )
        if mode == "search" and any(
            "/c/" in u for u in options["startUrls"]
        ):
            log.info(
                "Category grids stop at page %d (about %d listings per category). "
                "Split a broad category into its subcategories to go deeper.",
                CATEGORY_MAX_PAGE, CATEGORY_MAX_PAGE * 64,
            )
