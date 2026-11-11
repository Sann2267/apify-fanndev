"""Movie & TV Data Extractor - Apify Actor entrypoint."""

from __future__ import annotations

import logging
import os
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from . import parsers
from .client import TmdbAuthError, TmdbClient
from .constants import (
    DEFAULT_IMAGE_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    RESULTS_PER_PAGE,
)
from .markdown import render
from .modes import MODE_REQUIRED_INPUT, MODES, Budget, as_strings
from .parsers import error_record
from .input_errors import input_error

log = logging.getLogger("tmdb")

PUSH_BATCH = 100

# TMDB's terms require this line to be shown wherever their data is used. It is
# in the README, the store description and here, because a buyer who never
# reads the store page still has to see it once.
ATTRIBUTION = (
    "This product uses the TMDB API but is not endorsed or certified by TMDB."
)

# Which input arrays each mode reads, so a run can be given one list and the
# actor puts it where the chosen mode looks for it.
TARGET_KEYS = (
    "titleTargets",
    "personTargets",
    "tvTargets",
    "searchQueries",
    "collectionTargets",
    "companyTargets",
    "chartNames",
)


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator needs -- which target failed to resolve, how many pages a discover
    walk is about to read, how much of the item budget is left -- never appear.
    """
    actor_log = logging.getLogger("tmdb")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    TMDB is a keyed API with no IP gate: it serves a datacentre address exactly
    as it serves a residential one, and the rate limit follows the key rather
    than the address. Proxying therefore buys nothing here and is off by
    default. It is still offered, because a buyer behind a corporate egress
    sometimes needs a specific exit country for `region`-sensitive fields like
    watch providers.

    Setup failures never fail the run.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy. TMDB applies no IP gate, so the run "
            "should be unaffected.",
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


def _credential(actor_input: dict[str, Any]) -> str:
    """The TMDB key, from the input field or the environment.

    The environment fallback exists for local development and for buyers who
    set the key once as an Actor-level environment variable rather than in
    every run's input.
    """
    for source in (
        actor_input.get("tmdbApiKey"),
        os.environ.get("TMDB_API_KEY"),
        os.environ.get("TMDB_API_READ_ACCESS_TOKEN"),
    ):
        if source and str(source).strip():
            return str(source).strip()
    raise TmdbAuthError(
        "No TMDB credential supplied. This actor reads TMDB's official API, "
        "which needs a key of your own -- it is free and takes about a "
        "minute. Sign up at https://www.themoviedb.org/signup, open "
        "https://www.themoviedb.org/settings/api, and paste either the "
        "'API Key' or the 'API Read Access Token' into the tmdbApiKey field."
    )


def _format_record(rec: dict[str, Any], output_format: str) -> dict[str, Any]:
    """Attach or substitute the Markdown rendering, per the chosen format.

    A diagnostic row is never converted to Markdown even in `markdown` mode: a
    run that writes "no results" into a RAG corpus as prose has just taught
    someone's index a fact that is not about any film.
    """
    if output_format == "json":
        return rec
    markdown = render(rec.get("item_type", ""), rec.get("data") or {})
    if markdown is None:
        return rec
    if output_format == "markdown":
        return {
            "item_type": rec["item_type"],
            "id": rec["id"],
            "markdown": markdown,
            "metadata": rec["metadata"],
        }
    rec["markdown"] = markdown
    return rec


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "titleDetails"
        if mode not in MODES:
            raise input_error(f"Unknown mode {mode!r}. Valid modes: {', '.join(MODES)}")

        options = _collect_inputs(actor_input, mode)

        required = MODE_REQUIRED_INPUT.get(mode, ())
        if required and not any(options.get(key) for key in required):
            # Fail loud: a run with nothing to do should say so rather than
            # finishing green on an empty dataset.
            raise input_error(f"Mode {mode!r} needs at least one of: {', '.join(required)}.")

        output_format = str(actor_input.get("outputFormat") or "json").lower()
        if output_format not in ("json", "markdown", "both"):
            output_format = "json"

        parsers.configure(actor_input.get("imageSize") or DEFAULT_IMAGE_SIZE)

        max_items = int(actor_input.get("maxItems") or 0)
        log.info("Movie & TV Data Extractor | mode=%s maxItems=%s outputFormat=%s",
                 mode, max_items or "unlimited", output_format)
        log.info(ATTRIBUTION)

        if actor_input.get("fetchFullDetails") and mode in (
            "discoverTitles", "searchByName", "charts", "collectionTitles", "companyProfile"
        ):
            pages = int(actor_input.get("maxPagesPerTarget") or 5)
            log.info(
                "fetchFullDetails is ON: every one of the up-to-%d rows per "
                "target costs one extra TMDB request to expand into a full "
                "record. Turn it off for a cheap list-only run.",
                pages * RESULTS_PER_PAGE,
            )

        proxy_url = await _proxy_url(actor_input)
        client = TmdbClient(
            _credential(actor_input),
            proxy_url=proxy_url,
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            request_timeout=int(actor_input.get("requestTimeoutSecs") or DEFAULT_TIMEOUT_SECS),
            request_delay=float(actor_input.get("requestDelaySecs", DEFAULT_REQUEST_DELAY_SECS)),
            language=actor_input.get("language") or DEFAULT_LANGUAGE,
            region=actor_input.get("region") or None,
        )
        log.info(
            "Credential accepted as a %s.",
            "v4 read-access token (Authorization header)" if client.is_bearer
            else "v3 API key (query parameter)",
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
                        data.get("_error"), data.get("_input"), data.get("_errorDetail", ""),
                    )
                batch.append(_format_record(rec, output_format))
                if len(batch) >= PUSH_BATCH:
                    await flush()
            await flush()
        except TmdbAuthError as exc:
            await flush()
            log.error("%s", exc)
            await Actor.push_data(
                error_record(f"mode:{mode}", "auth_failed", str(exc), mode=mode)
            )
            raise
        except Exception as exc:  # noqa: BLE001 - the run must still leave a trace
            await flush()
            log.exception("Mode %s failed", mode)
            await Actor.push_data(
                error_record(
                    f"mode:{mode}", "run_failed", f"{type(exc).__name__}: {exc}", mode=mode,
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
            "retried after a pause; raise requestDelaySecs if that number is large."
            if client.rate_limited_count else ""
        )
        log.info(
            "Done. %d records pushed (%d diagnostic error rows) from %d TMDB "
            "API requests.%s",
            pushed, errors, client.request_count, rate_note,
        )
        log.info(ATTRIBUTION)
