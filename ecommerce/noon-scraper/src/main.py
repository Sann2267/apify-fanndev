"""noon.com Scraper - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import NoonBlocked, NoonClient
from .constants import (
    COUNTRIES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    LANGUAGES,
    MAX_CONCURRENCY,
)
from .modes import MODE_REQUIRED_INPUT, MODES, Budget
from .parsers import as_strings, error_record, locale_of
from .input_errors import input_error

log = logging.getLogger("noon")

PUSH_BATCH = 100

# Input arrays a run can fill; `targets` routes into whichever one the chosen
# mode reads, so the actor can be chained from another actor with one list.
TARGET_KEYS = ("searchKeywords", "categoryPaths", "brandCodes", "productSkus")


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator actually needs -- how many products a category really held, when
    pagination hit its end, when the item budget ran out -- never appear.
    """
    actor_log = logging.getLogger("noon")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    Proxying is genuinely OPTIONAL for this actor, and that is a measured
    claim: the catalogue gateway served every mode to a plain, unproxied
    address during recon -- no WAF, no TLS gate, 30/30 concurrent requests at
    ~8.8 req/s -- from a network that noon's own Akamai edge denies outright.

    Where a proxy does earn its cost:
      * RESIDENTIAL in AE/SA/EG is the only way the S2 fallback host
        (www.noon.com) can ever answer, since that host sits behind the Akamai
        ACL.
      * Rate-limit headroom on very large catalogue walks.

    A setup failure never fails the run: a plan without the Proxy
    external-access feature continues direct and says so.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(
            actor_proxy_input=cfg
        )
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy. noon's catalogue gateway answers "
            "unproxied addresses, so the run should still work; only "
            "rate-limit headroom and the S2 fallback are lost.",
            type(exc).__name__, exc,
        )
        return None
    if proxy_configuration is None:
        log.warning("Proxy was requested but no configuration came back; going direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info("Using Apify Proxy (groups=%s, country=%s)",
             cfg.get("apifyProxyGroups") or "auto",
             cfg.get("apifyProxyCountry") or "any")
    return url


def _collect_inputs(actor_input: dict[str, Any], mode: str) -> dict[str, Any]:
    """Normalise every input field into the shape the modes expect."""
    options: dict[str, Any] = dict(actor_input)
    for key in TARGET_KEYS:
        options[key] = as_strings(actor_input.get(key))

    generic = as_strings(actor_input.get("targets"))
    if generic:
        required = MODE_REQUIRED_INPUT.get(mode, ())
        if required and not options.get(required[0]):
            options[required[0]] = generic
            log.info("Routed %d value(s) from 'targets' into '%s' for mode %s.",
                     len(generic), required[0], mode)

    country = str(actor_input.get("country") or "ae").lower()
    language = str(actor_input.get("language") or "en").lower()
    if country not in COUNTRIES:
        raise ValueError(
            f"Unknown country {country!r}. noon serves: {', '.join(COUNTRIES)}."
        )
    if language not in LANGUAGES:
        raise ValueError(
            f"Unknown language {language!r}. Valid: {', '.join(LANGUAGES)}."
        )
    options["country"] = country
    options["language"] = language
    options["locale"] = locale_of(country, language)
    options["concurrency"] = max(
        1, min(int(actor_input.get("concurrency") or 4), MAX_CONCURRENCY)
    )
    return options


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "search"
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
            "noon Scraper | mode=%s locale=%s maxItems=%s limitPerPage=%s maxPages=%s",
            mode, options["locale"], max_items or "unlimited",
            options.get("limitPerPage") or "default (200)",
            options.get("maxPages") or "default",
        )

        proxy_url = await _proxy_url(actor_input)
        client = NoonClient(
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(
                actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS
            ),
            request_delay=float(
                actor_input.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS)
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
                if max_items and pushed + len(batch) >= max_items:
                    log.info("Reached maxItems=%d; stopping.", max_items)
                    break
                if rec.get("_error"):
                    errors += 1
                    log.warning("%s [%s]: %s", rec.get("_error"), rec.get("_input"),
                                rec.get("_errorDetail", ""))
                batch.append(rec)
                if len(batch) >= PUSH_BATCH:
                    await flush()
            await flush()
        except NoonBlocked as exc:
            # The one failure worth shouting about: both hosts refused us, so
            # no mode can work from this network until a proxy is added.
            await flush()
            log.error("%s", exc)
            await Actor.push_data(error_record(
                f"mode:{mode}", "blocked", str(exc),
                country=options["country"], language=options["language"], mode=mode,
            ))
            pushed += 1
            raise
        except Exception as exc:  # noqa: BLE001 - the run must still leave a trace
            await flush()
            log.exception("Mode %s failed", mode)
            await Actor.push_data(error_record(
                f"mode:{mode}", "run_failed", f"{type(exc).__name__}: {exc}",
                country=options["country"], language=options["language"], mode=mode,
            ))
            pushed += 1
            raise
        finally:
            await client.close()

        if pushed == 0:
            # Never finish with an empty dataset -- downstream joins read that
            # as a crash rather than as "nothing matched".
            await Actor.push_data(error_record(
                f"mode:{mode}", "no_results",
                f"Mode {mode} produced no records for the given input.",
                country=options["country"], language=options["language"], mode=mode,
            ))
            pushed = 1

        log.info("Done. mode=%s records=%d errors=%d", mode, pushed, errors)
