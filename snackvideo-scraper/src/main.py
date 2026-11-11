"""SnackVideo Scraper - Apify Actor entrypoint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import SnackBlocked, SnackClient, SnackError
from .constants import DEFAULT_MAX_RETRIES
from .modes import MODES, Options
from .parsers import error_record

log = logging.getLogger("snackvideo")

PUSH_BATCH = 50


def _configure_logging() -> None:
    """The SDK only wires the 'apify' logger; route ours into the run log too."""
    root = logging.getLogger("snackvideo")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False


async def _proxy_configuration(actor_input: dict[str, Any]) -> Any:
    """Apify Proxy if asked for, otherwise direct.

    SnackVideo has no WAF, so a proxy is not what makes requests succeed. What
    it changes is WHICH content you get: the For You and search feeds are
    localised by exit-IP country (a Jakarta IP gets the Indonesian bucket).
    Setup failures never fail the run - a local run without a token continues
    direct and says so.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested - requests go out direct.")
        return None
    try:
        pc = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxy is optional for this target
        log.warning("Apify Proxy could not be set up (%s: %s). Continuing WITHOUT a proxy - "
                    "SnackVideo serves every endpoint to unproxied clients.", type(exc).__name__, exc)
        return None
    if pc is None:
        log.warning("Apify Proxy returned no configuration. Continuing without a proxy.")
    return pc


def _as_strings(value: Any) -> list[str]:
    out: list[str] = []
    for v in value or []:
        if isinstance(v, dict):  # requestListSources-style {"url": ...}
            v = v.get("url")
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return list(dict.fromkeys(out))  # dedupe, keep order


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "trending"
        if mode not in MODES:
            await Actor.fail(status_message=f"Unknown mode {mode!r}. Use one of: {', '.join(MODES)}")
            return
        runner, field = MODES[mode]

        targets = ["foryou"] if field is None else _as_strings(actor_input.get(field))
        if not targets:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in '{field}'.")
            return

        opt = Options(
            max_items=max(1, int(actor_input.get("maxItems") or 100)),
            include_videos=bool(actor_input.get("includeVideos", True)),
            include_playlists=bool(actor_input.get("includePlaylists", True)),
            include_manifest=bool(actor_input.get("includeStreamManifest", False)),
            only_keyword_matches=bool(actor_input.get("onlyKeywordMatches", False)),
        )
        concurrency = max(1, min(10, int(actor_input.get("maxConcurrency") or 3)))
        max_retries = max(1, int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES))
        proxy_configuration = await _proxy_configuration(actor_input)

        log.info("Mode=%s targets=%d maxItems=%d concurrency=%d", mode, len(targets), opt.max_items, concurrency)

        stats = {"records": 0, "errors": 0, "requests": 0}
        push_lock = asyncio.Lock()
        sem = asyncio.Semaphore(concurrency)

        async def push(batch: list[dict[str, Any]]) -> None:
            if not batch:
                return
            async with push_lock:
                await Actor.push_data(batch)
                stats["records"] += len(batch)
                stats["errors"] += sum(1 for r in batch if r.get("_error"))

        async def process(target: str) -> None:
            async with sem:
                client = SnackClient(proxy_configuration, max_retries=max_retries)
                batch: list[dict[str, Any]] = []
                count = 0
                try:
                    async for record in runner(client, target, opt):
                        batch.append(record)
                        count += 1
                        if len(batch) >= PUSH_BATCH:
                            await push(batch)
                            batch = []
                except SnackBlocked as exc:
                    log.error("%s: gave up - %s", target, exc)
                    batch.append(error_record(target, "blocked", str(exc)))
                except SnackError as exc:
                    log.error("%s: API error - %s", target, exc)
                    batch.append(error_record(target, "api_error", str(exc)))
                except Exception as exc:  # noqa: BLE001 - one bad target must not kill the run
                    log.exception("%s: unexpected failure", target)
                    batch.append(error_record(target, "exception", f"{type(exc).__name__}: {exc}"))
                finally:
                    await push(batch)
                    stats["requests"] += client.request_count
                    await client.close()
                log.info("%s: %d records (%d requests)", target, count, client.request_count)
                await Actor.set_status_message(
                    f"{mode}: {stats['records']} records, {stats['errors']} errors so far"
                )

        await asyncio.gather(*(process(t) for t in targets))

        summary = (f"Done. mode={mode} targets={len(targets)} records={stats['records']} "
                   f"errors={stats['errors']} requests={stats['requests']}")
        log.info(summary)
        await Actor.set_status_message(summary, is_terminal=True)
