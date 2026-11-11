"""Steam Review & Sentiment Analyzer - Apify Actor entrypoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import Pacers, SteamBlocked, SteamClient, SteamError, SteamNotFound
from .constants import (
    DEFAULT_MAX_RETRIES,
    LANGUAGES,
    PURCHASE_TYPES,
    REVIEW_FILTERS,
    REVIEW_TYPES,
)
from .modes import MODES, InputError, Options, parse_date
from .parsers import error_record

log = logging.getLogger("steam")

PUSH_BATCH = 100
# Stop starting new work this long before the run timeout so the last
# batches still get pushed and the run ends SUCCEEDED, not TIMED-OUT.
TIMEOUT_MARGIN = timedelta(seconds=45)


def _configure_logging() -> None:
    """The SDK only wires the 'apify' logger; route ours into the run log too."""
    root = logging.getLogger("steam")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False


async def _proxy_configuration(actor_input: dict[str, Any]) -> Any:
    """Apify Proxy if asked for, otherwise direct.

    Steam has no WAF; the proxy is a throughput tool. /appreviews/ is rate
    limited per IP (~46 req/min sustained), so each worker gets its own exit
    IP and a 429 swaps the IP instead of waiting 30-60 s. Setup failures never
    fail the run - it continues direct and paces itself.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested - requests go out direct and are paced to Steam's per-IP limit.")
        return None
    try:
        pc = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxy is optional for this target
        log.warning("Apify Proxy could not be set up (%s: %s). Continuing WITHOUT a proxy - Steam serves every "
                    "endpoint to unproxied clients, just slower under the rate limit.", type(exc).__name__, exc)
        return None
    if pc is None:
        log.warning("Apify Proxy returned no configuration. Continuing without a proxy.")
    return pc


def _as_strings(value: Any) -> list[str]:
    out: list[str] = []
    for v in value or []:
        if isinstance(v, dict):  # requestListSources-style {"url": ...}
            v = v.get("url")
        if isinstance(v, (str, int)) and str(v).strip():
            out.append(str(v).strip())
    return list(dict.fromkeys(out))


def _choice(actor_input: dict[str, Any], key: str, default: str, allowed: set[str]) -> str:
    value = str(actor_input.get(key) or default)
    if value not in allowed:
        raise InputError(f"'{key}' must be one of {sorted(allowed)}, got {value!r}")
    return value


def _build_options(actor_input: dict[str, Any]) -> Options:
    language = str(actor_input.get("language") or "all")
    # Steam answers an unknown language code with a hollow "No user reviews"
    # 200, so a typo would silently look like a game with zero reviews.
    if language != "all" and language not in LANGUAGES:
        raise InputError(f"Unknown Steam language code {language!r}. Use 'all' or one of: {', '.join(LANGUAGES)}")
    langs = _as_strings(actor_input.get("languages"))
    bad = [l for l in langs if l not in LANGUAGES]
    if bad:
        raise InputError(f"Unknown language code(s) in 'languages': {bad}. Allowed: {', '.join(LANGUAGES)}")
    min_pt = actor_input.get("minPlaytimeHours")
    max_pt = actor_input.get("maxPlaytimeHours")
    opt = Options(
        max_reviews=max(1, int(actor_input.get("maxReviewsPerApp") or 500)),
        review_filter=_choice(actor_input, "sortBy", "recent", REVIEW_FILTERS),
        language=language,
        purchase_type=_choice(actor_input, "purchaseType", "all", PURCHASE_TYPES),
        review_type=_choice(actor_input, "reviewType", "all", REVIEW_TYPES),
        day_range=max(1, min(365, int(actor_input.get("helpfulDayRange") or 365))),
        min_playtime_hours=int(min_pt) if min_pt else None,
        max_playtime_hours=int(max_pt) if max_pt else None,
        include_offtopic=bool(actor_input.get("includeOffTopicReviews", False)),
        start_ts=parse_date(actor_input.get("startDate")),
        end_ts=parse_date(actor_input.get("endDate"), end_of_day=True),
        text_sentiment=bool(actor_input.get("textSentiment", True)),
        breakdown_languages=langs,
        sample_size=max(0, min(5000, int(actor_input.get("sampleSize") if actor_input.get("sampleSize") is not None else 300))),
        country=str(actor_input.get("country") or "us").lower(),
    )
    if opt.start_ts and opt.end_ts and opt.start_ts > opt.end_ts:
        raise InputError("'startDate' is after 'endDate'.")
    return opt


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "summary"
        if mode not in MODES:
            await Actor.fail(status_message=f"Unknown mode {mode!r}. Use one of: {', '.join(MODES)}")
            return
        runner, field = MODES[mode]
        targets = _as_strings(actor_input.get(field))
        if not targets:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in '{field}'.")
            return
        try:
            opt = _build_options(actor_input)
        except (InputError, ValueError, TypeError) as exc:
            await Actor.fail(status_message=f"Invalid input: {exc}")
            return

        concurrency = max(1, min(10, int(actor_input.get("maxConcurrency") or 3)))
        max_retries = max(1, int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES))
        proxy_configuration = await _proxy_configuration(actor_input)
        if actor_input.get("debugReviewsIntervalSecs") is not None:
            Pacers.reviews_interval = max(0.0, float(actor_input["debugReviewsIntervalSecs"]))
            log.warning("Test hook: review pacing set to %.2f s", Pacers.reviews_interval)
        # Direct: every worker leaves from the same IP, so they share one pacer.
        shared_pacers = Pacers() if proxy_configuration is None else None

        deadline = None
        if Actor.configuration.timeout_at:
            deadline = Actor.configuration.timeout_at - TIMEOUT_MARGIN

        log.info("Mode=%s targets=%d maxReviewsPerApp=%d sortBy=%s language=%s purchaseType=%s concurrency=%d proxy=%s",
                 mode, len(targets), opt.max_reviews, opt.review_filter, opt.language, opt.purchase_type,
                 concurrency, "yes" if proxy_configuration else "no")

        stats = {"records": 0, "errors": 0, "requests": 0}
        push_lock = asyncio.Lock()
        sem = asyncio.Semaphore(concurrency)
        stopping = asyncio.Event()

        async def push(batch: list[dict[str, Any]]) -> None:
            if not batch:
                return
            async with push_lock:
                await Actor.push_data(batch)
                stats["records"] += len(batch)
                stats["errors"] += sum(1 for r in batch if r.get("_error"))

        def out_of_time() -> bool:
            from datetime import datetime, timezone

            if deadline and datetime.now(timezone.utc) >= deadline:
                if not stopping.is_set():
                    log.warning("Approaching the run timeout - stopping gracefully and saving what was collected.")
                    stopping.set()
                return True
            return False

        async def process(target: str) -> None:
            async with sem:
                if out_of_time():
                    return
                client = SteamClient(proxy_configuration, shared_pacers, max_retries=max_retries)
                batch: list[dict[str, Any]] = []
                count = 0
                try:
                    async for record in runner(client, target, opt):
                        batch.append(record)
                        count += 1
                        if len(batch) >= PUSH_BATCH:
                            await push(batch)
                            batch = []
                        if out_of_time():
                            break
                except SteamNotFound as exc:
                    log.warning("%s: not found - %s", target, exc)
                    batch.append(error_record(target, "not_found", str(exc)))
                except InputError as exc:
                    log.warning("%s: bad input - %s", target, exc)
                    batch.append(error_record(target, "invalid_input", str(exc)))
                except SteamBlocked as exc:
                    log.error("%s: gave up - %s", target, exc)
                    batch.append(error_record(target, "blocked", str(exc)))
                except SteamError as exc:
                    log.error("%s: Steam error - %s", target, exc)
                    batch.append(error_record(target, "api_error", str(exc)))
                except Exception as exc:  # noqa: BLE001 - one bad target must not kill the run
                    log.exception("%s: unexpected failure", target)
                    batch.append(error_record(target, "exception", f"{type(exc).__name__}: {exc}"))
                finally:
                    await push(batch)
                    stats["requests"] += client.request_count
                    await client.close()
                log.info("%s: %d records (%d requests)", target, count, client.request_count)
                await Actor.set_status_message(f"{mode}: {stats['records']} records, {stats['errors']} errors so far")

        await asyncio.gather(*(process(t) for t in targets))

        summary = (f"Done. mode={mode} targets={len(targets)} records={stats['records']} "
                   f"errors={stats['errors']} requests={stats['requests']}"
                   + (" (stopped early: run timeout)" if stopping.is_set() else ""))
        log.info(summary)
        await Actor.set_status_message(summary, is_terminal=True)
