"""Steam Profile & Achievement Extractor - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import Blocked, NotFound, SteamClient
from .constants import DEFAULT_HTML_CONCURRENCY, DEFAULT_MAX_RETRIES
from .modes import MODES, NEEDS_APPS, NEEDS_GROUPS, NEEDS_PROFILES, Options
from .parsers import UnexpectedShape, error_record

log = logging.getLogger("steam")

PUSH_BATCH = 100


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

    Steam has no WAF; the proxy exists for the per-IP HTML rate limit (each 429
    swaps the exit IP instead of waiting ~45 s). Setup failures never fail the
    run: a local run without a token continues direct and says so.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested - requests go out direct (HTML 429s are waited out, ~45 s each).")
        return None
    try:
        pc = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxy is optional for this target
        log.warning("Apify Proxy could not be set up (%s: %s). Continuing WITHOUT a proxy.", type(exc).__name__, exc)
        return None
    if pc is None:
        log.warning("Apify Proxy returned no configuration. Continuing without a proxy.")
    return pc


def _clean_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = values.replace(",", "\n").splitlines()
    return list(dict.fromkeys(str(v).strip() for v in (values or []) if str(v).strip()))


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "profiles"
        if mode not in MODES:
            await Actor.fail(status_message=f"Unknown mode {mode!r}. Use one of: {', '.join(MODES)}")
            return

        opt = Options(
            profiles=_clean_list(actor_input.get("profiles")),
            app_ids=_clean_list(actor_input.get("appIds")),
            groups=_clean_list(actor_input.get("groups")),
            max_items=max(1, int(actor_input.get("maxItems") or 1000)),
            max_games_per_profile=max(1, int(actor_input.get("maxGamesPerProfile") or 10)),
            include_profile_page=bool(actor_input.get("includeProfilePage", True)),
            include_equipped_items=bool(actor_input.get("includeEquippedItems", False)),
            flatten_achievements=bool(actor_input.get("flattenAchievements", False)),
            only_unlocked=bool(actor_input.get("onlyUnlocked", False)),
            enrich_profiles=bool(actor_input.get("enrichProfiles", False)),
            language=(actor_input.get("language") or "english").strip().lower(),
            concurrency=max(1, min(20, int(actor_input.get("maxConcurrency") or 8))),
        )
        if mode in NEEDS_PROFILES and not opt.profiles:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in 'profiles' (SteamID64, profile URL or vanity name).")
            return
        if mode in NEEDS_APPS and not opt.app_ids:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in 'appIds' (appid or Steam app URL).")
            return
        if mode in NEEDS_GROUPS and not opt.groups:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in 'groups' (group URL or name).")
            return

        max_retries = max(1, int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES))
        proxy = await _proxy_configuration(actor_input)
        client = SteamClient(proxy, max_retries=max_retries, concurrency=opt.concurrency,
                             html_concurrency=(opt.concurrency if proxy else DEFAULT_HTML_CONCURRENCY))

        log.info("Mode=%s profiles=%d appIds=%d groups=%d maxItems=%d language=%s concurrency=%d",
                 mode, len(opt.profiles), len(opt.app_ids), len(opt.groups), opt.max_items, opt.language, opt.concurrency)

        stats = {"records": 0, "errors": 0}
        batch: list[dict[str, Any]] = []

        async def flush() -> None:
            nonlocal batch
            if batch:
                await Actor.push_data(batch)
                stats["records"] += len(batch)
                stats["errors"] += sum(1 for r in batch if r.get("_error"))
                batch = []

        try:
            async for rec in MODES[mode](client, opt):
                batch.append(rec)
                if len(batch) >= PUSH_BATCH:
                    await flush()
                    await Actor.set_status_message(f"{mode}: {stats['records']} records so far")
        except (Blocked, NotFound) as exc:
            log.error("%s: upstream failure - %s", mode, exc)
            batch.append(error_record(mode, "blocked" if isinstance(exc, Blocked) else "not_found", str(exc)))
        except UnexpectedShape as exc:
            log.error("%s: upstream layout changed - %s", mode, exc)
            batch.append(error_record(mode, "unexpected_shape", str(exc)))
        finally:
            await flush()
            await client.close()

        ok = stats["records"] - stats["errors"]
        summary = (f"Done. mode={mode} records={ok} errors={stats['errors']} "
                   f"requests={client.request_count} rateLimited={client.rate_limited}")
        log.info(summary)
        if ok == 0 and stats["errors"]:
            await Actor.fail(status_message=summary + " - every input failed, see the dataset for reasons.")
            return
        await Actor.set_status_message(summary, is_terminal=True)
