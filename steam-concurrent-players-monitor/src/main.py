"""Steam Concurrent Players Monitor - Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import Blocked, NotFound, SteamClient
from .constants import DEFAULT_MAX_RETRIES, SNAPSHOT_STORE
from .modes import MODES, MONITORED_METRIC, NEEDS_APPS, Options
from .parsers import UnexpectedShape, error_record, utc_now_iso

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

    No surface here has a WAF or an IP gate (recon 2026-10-11), so a proxy is
    not what makes requests succeed - it is there for a future rate limit.
    Setup failures never fail the run: a local run without a token continues
    direct and says so.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested - requests go out direct (no WAF on any Steam surface used).")
        return None
    try:
        pc = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxy is optional for this target
        log.warning("Apify Proxy could not be set up (%s: %s). Continuing WITHOUT a proxy.", type(exc).__name__, exc)
        return None
    if pc is None:
        log.warning("Apify Proxy returned no configuration. Continuing without a proxy.")
    return pc


class ChangeTracker:
    """Compares each record with the same app's value from the previous run.

    Snapshots live in a NAMED key-value store, so they survive between
    scheduled runs (the default store is per-run). One key per mode; entries
    are merged, so several tasks watching different app lists share it safely.
    """

    def __init__(self, mode: str, alert_pct: float) -> None:
        self.key = f"snapshot-{mode}"
        self.alert_pct = alert_pct
        self.store: Any = None
        self.prev: dict[str, Any] = {}
        self.next: dict[str, Any] = {}

    async def load(self) -> None:
        self.store = await Actor.open_key_value_store(name=SNAPSHOT_STORE)
        snap = await self.store.get_value(self.key) or {}
        self.prev = snap.get("entries") or {}
        self.next = dict(self.prev)
        log.info("Change detection: %d entries in previous snapshot '%s'", len(self.prev), self.key)

    def apply(self, rec: dict[str, Any]) -> None:
        metric = MONITORED_METRIC.get(rec.get("recordType", ""))
        if not metric or rec.get(metric) is None:
            return
        key = str(rec.get("appid") or rec.get("label") or rec["_input"])
        value = rec[metric]
        old = self.prev.get(key)
        if old is None:
            rec.update(previousPlayers=None, playersChange=None, playersChangePct=None,
                       previousRank=None, rankChange=None, previousSnapshotAt=None, isNewEntry=bool(self.prev))
        else:
            change = value - old["value"]
            pct = round(change / old["value"] * 100, 2) if old["value"] else None
            prank = old.get("rank")
            rec.update(previousPlayers=old["value"], playersChange=change, playersChangePct=pct,
                       previousRank=prank,
                       rankChange=(prank - rec["rank"]) if prank and rec.get("rank") else None,
                       previousSnapshotAt=old.get("at"), isNewEntry=False)
            # The upstream chart refreshes every few minutes (topConcurrent) or once
            # a day (topDailyPeak): a 0 delta inside one refresh is not "no movement".
            upstream = rec.get("lastUpdate") or rec.get("rollupDate") or rec.get("currentPlayersAt") or rec.get("usersOnlineAt")
            if upstream and old.get("upstreamAt"):
                rec["sameUpstreamSnapshot"] = upstream == old["upstreamAt"]
            if self.alert_pct > 0:
                rec["alert"] = pct is not None and abs(pct) >= self.alert_pct
        self.next[key] = {"value": value, "rank": rec.get("rank"), "at": rec["_scrapedAt"],
                         "upstreamAt": rec.get("lastUpdate") or rec.get("rollupDate")
                         or rec.get("currentPlayersAt") or rec.get("usersOnlineAt")}

    async def save(self) -> None:
        if self.store is not None:
            await self.store.set_value(self.key, {"savedAt": utc_now_iso(), "entries": self.next})


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "topConcurrent"
        if mode not in MODES:
            await Actor.fail(status_message=f"Unknown mode {mode!r}. Use one of: {', '.join(MODES)}")
            return

        apps = [a for a in (actor_input.get("apps") or []) if str(a).strip()]
        if mode in NEEDS_APPS and not apps:
            await Actor.fail(status_message=f"Mode '{mode}' needs at least one entry in 'apps' (appid, Steam URL or game name).")
            return

        opt = Options(
            apps=list(dict.fromkeys(str(a).strip() for a in apps)),
            max_items=max(1, int(actor_input.get("maxItems") or 100)),
            min_players=max(0, int(actor_input.get("minPlayers") or 0)),
            include_store_details=bool(actor_input.get("includeStoreDetails", True)),
            include_steamcharts_stats=bool(actor_input.get("includeSteamchartsStats", False)),
            include_series=bool(actor_input.get("includeSeries", True)),
            history_days=max(0, int(actor_input.get("historyDays") or 0)),
            country=(actor_input.get("country") or "US").upper(),
            language=actor_input.get("language") or "english",
            concurrency=max(1, min(16, int(actor_input.get("maxConcurrency") or 5))),
        )
        max_retries = max(1, int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES))
        client = SteamClient(await _proxy_configuration(actor_input), max_retries=max_retries)

        tracker = None
        if actor_input.get("compareWithPrevious", True):
            tracker = ChangeTracker(mode, float(actor_input.get("alertChangePct") or 0))
            await tracker.load()

        log.info("Mode=%s apps=%d maxItems=%d minPlayers=%d concurrency=%d",
                 mode, len(opt.apps), opt.max_items, opt.min_players, opt.concurrency)

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
                if tracker and not rec.get("_error"):
                    tracker.apply(rec)
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

        if tracker:
            await tracker.save()

        ok = stats["records"] - stats["errors"]
        summary = f"Done. mode={mode} records={ok} errors={stats['errors']} requests={client.request_count}"
        log.info(summary)
        if ok == 0 and stats["errors"]:
            await Actor.fail(status_message=summary + " - every input failed, see the dataset for reasons.")
            return
        await Actor.set_status_message(summary, is_terminal=True)
