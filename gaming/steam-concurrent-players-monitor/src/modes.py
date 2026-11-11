"""One async generator per mode. Each yields finished records (envelope included)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from .client import Blocked, NotFound, SteamClient
from .constants import (
    RESULT_NO_MATCH,
    STEAMCHARTS,
    STEAMCHARTS_TOP_PAGE_SIZE,
    STORE_ITEMS_BATCH,
    URL_CURRENT_PLAYERS,
    URL_STEAM_ONLINE,
    URL_STORE_ITEMS,
    URL_STORE_SEARCH,
    URL_TOP_CONCURRENT,
    URL_TOP_DAILY_PEAK,
)
from .parsers import (
    UnexpectedShape,
    envelope,
    error_record,
    parse_app_ref,
    parse_chart_data,
    parse_steamcharts_app,
    parse_steamcharts_top,
    store_item_summary,
    unix_to_iso,
    utc_now_iso,
)

log = logging.getLogger("steam.modes")


@dataclass
class Options:
    apps: list[Any] = field(default_factory=list)
    max_items: int = 100
    min_players: int = 0
    include_store_details: bool = True
    include_steamcharts_stats: bool = False
    include_series: bool = True
    history_days: int = 0
    country: str = "US"
    language: str = "english"
    concurrency: int = 5


def _context(opt: Options) -> dict[str, Any]:
    return {"language": opt.language, "country_code": opt.country}


def _data_request() -> dict[str, Any]:
    return {"include_basic_info": True, "include_release": True}


async def store_items(client: SteamClient, appids: list[int], opt: Options) -> dict[int, dict[str, Any]]:
    """Batch-fetch store items (names, developers, release) for many appids."""
    out: dict[int, dict[str, Any]] = {}
    for i in range(0, len(appids), STORE_ITEMS_BATCH):
        chunk = appids[i:i + STORE_ITEMS_BATCH]
        body = {"ids": [{"appid": a} for a in chunk], "context": _context(opt), "data_request": _data_request()}
        try:
            data = await client.get_json(URL_STORE_ITEMS, {"input_json": json.dumps(body)})
        except (Blocked, NotFound) as exc:
            log.warning("Store details lookup failed for %d apps (%s) - continuing without names", len(chunk), exc)
            continue
        for item in (data.get("response") or {}).get("store_items") or []:
            if item.get("appid") or item.get("id"):
                out[int(item.get("appid") or item.get("id"))] = item
    return out


async def resolve_apps(client: SteamClient, refs: list[Any], opt: Options) -> tuple[list[tuple[str, int, str | None]], list[dict[str, Any]]]:
    """Turn ids / URLs / game names into (input, appid, matchedName). Unresolvable -> ERROR records."""
    resolved: list[tuple[str, int, str | None]] = []
    errors: list[dict[str, Any]] = []
    for ref in refs:
        label = str(ref).strip()
        appid, term = parse_app_ref(ref)
        if appid:
            resolved.append((label, appid, None))
            continue
        if not term:
            errors.append(error_record(label, "invalid_input", "Not an appid, a Steam/SteamCharts/SteamDB app URL, or a game name."))
            continue
        try:
            data = await client.get_json(URL_STORE_SEARCH, {"term": term, "cc": opt.country, "l": opt.language})
        except (Blocked, NotFound) as exc:
            errors.append(error_record(label, "search_failed", str(exc)))
            continue
        hits = [it for it in data.get("items") or [] if it.get("type") == "app" and it.get("id")]
        if not hits:
            errors.append(error_record(label, "not_found", f"Steam store search returned no game for {term!r}."))
            continue
        # Prefer an exact (case-insensitive) title match over Steam's relevance order.
        exact = [h for h in hits if (h.get("name") or "").casefold() == term.casefold()]
        best = (exact or hits)[0]
        log.info("Resolved %r -> %s (%s)", term, best["id"], best.get("name"))
        resolved.append((label, int(best["id"]), best.get("name")))
    # Same app given twice (id + URL) - keep the first.
    seen: set[int] = set()
    unique = [r for r in resolved if not (r[1] in seen or seen.add(r[1]))]
    return unique, errors


# --------------------------------------------------------------------------- modes

async def top_concurrent(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Steam's live 'Most Played' chart: top 100 by players in-game right now + today's peak."""
    body: dict[str, Any] = {"context": _context(opt)}
    if opt.include_store_details:
        body["data_request"] = _data_request()
    data = await client.get_json(URL_TOP_CONCURRENT, {"input_json": json.dumps(body)})
    resp = data.get("response") or {}
    ranks = resp.get("ranks")
    if not isinstance(ranks, list) or not ranks:
        raise UnexpectedShape("GetGamesByConcurrentPlayers returned no ranks")
    updated = unix_to_iso(resp.get("last_update"))
    n = 0
    for row in ranks:
        if n >= opt.max_items:
            break
        if (row.get("concurrent_in_game") or 0) < opt.min_players:
            continue
        item = row.pop("item", None)
        yield envelope("topConcurrent", "S1-steam-api-concurrent", "TOP_CONCURRENT",
                       **row, **store_item_summary(item), lastUpdate=updated,
                       **({"item": item} if item else {}))
        n += 1


async def top_daily_peak(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Steam's daily 'Most Played' rollup: top 100 by yesterday's peak, with last week's rank.

    `top_played_period` is accepted by the API but ignored (periods 0-4 return
    byte-identical data, 2026-10-11), so it is not exposed.
    """
    body: dict[str, Any] = {"context": _context(opt)}
    if opt.include_store_details:
        body["data_request"] = _data_request()
    data = await client.get_json(URL_TOP_DAILY_PEAK, {"input_json": json.dumps(body)})
    resp = data.get("response") or {}
    ranks = resp.get("ranks")
    if not isinstance(ranks, list) or not ranks:
        raise UnexpectedShape("GetMostPlayedGames returned no ranks")
    rollup = unix_to_iso(resp.get("rollup_date"))
    n = 0
    for row in ranks:
        if n >= opt.max_items:
            break
        if (row.get("peak_in_game") or 0) < opt.min_players:
            continue
        item = row.pop("item", None)
        lwr = row.get("last_week_rank")
        yield envelope("topDailyPeak", "S1-steam-api-mostplayed", "TOP_DAILY_PEAK",
                       **row, rankChangeVsLastWeek=(lwr - row["rank"]) if lwr else None,
                       **store_item_summary(item), rollupDate=rollup,
                       **({"item": item} if item else {}))
        n += 1


async def _bounded_map(items: list[Any], conc: int, fn: Callable[[Any], Awaitable[Any]]) -> list[Any]:
    sem = asyncio.Semaphore(conc)

    async def one(x: Any) -> Any:
        async with sem:
            return await fn(x)

    return await asyncio.gather(*(one(x) for x in items))


async def _steamcharts_app(client: SteamClient, appid: int) -> dict[str, Any] | None:
    try:
        return parse_steamcharts_app(await client.get_text(f"{STEAMCHARTS}/app/{appid}"))
    except NotFound:
        return None


async def apps_current(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Live player count for each requested app (official API, any appid)."""
    apps, errors = await resolve_apps(client, opt.apps, opt)
    for e in errors:
        yield e
    if not apps:
        return
    items = await store_items(client, [a for _, a, _ in apps], opt) if opt.include_store_details else {}

    async def one(entry: tuple[str, int, str | None]) -> dict[str, Any]:
        label, appid, matched = entry
        try:
            data = await client.get_json(URL_CURRENT_PLAYERS, {"appid": appid})
        except NotFound as exc:
            return error_record(label, "not_found", f"Steam has no player count for appid {appid} ({exc}).", appid=appid)
        except Blocked as exc:
            return error_record(label, "blocked", str(exc), appid=appid)
        resp = data.get("response") or {}
        if resp.get("result") == RESULT_NO_MATCH or "player_count" not in resp:
            return error_record(label, "not_found", f"Steam has no player count for appid {appid} (result={resp.get('result')}).", appid=appid)
        rec = envelope(label, "S1-steam-api-current", "APP_CURRENT", appid=appid, player_count=resp["player_count"],
                       **store_item_summary(items.get(appid)), checkedAt=utc_now_iso())
        if matched and not rec.get("name"):
            rec["name"] = matched
        if opt.include_steamcharts_stats:
            try:
                sc = await _steamcharts_app(client, appid)
            except (Blocked, UnexpectedShape) as exc:
                sc, rec["steamchartsError"] = None, str(exc)
            if sc:
                rec.update(peak24h=sc["peak24h"], allTimePeak=sc["allTimePeak"],
                           avgPlayersLast30Days=sc["months"][0]["avgPlayers"] if sc["months"][0]["month"] == "Last 30 Days" else None)
                rec["name"] = rec.get("name") or sc["name"]
            elif "steamchartsError" not in rec:
                rec["steamchartsError"] = "not tracked by steamcharts.com"
        return rec

    for rec in await _bounded_map(apps, opt.concurrency, one):
        yield rec


async def app_history(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """Per-app history from steamcharts.com: monthly avg/gain/peak since launch + point series."""
    apps, errors = await resolve_apps(client, opt.apps, opt)
    for e in errors:
        yield e
    if not apps:
        return
    cutoff_ms = None
    if opt.history_days > 0:
        import time
        cutoff_ms = (time.time() - opt.history_days * 86400) * 1000

    async def one(entry: tuple[str, int, str | None]) -> dict[str, Any]:
        label, appid, matched = entry
        try:
            page = await _steamcharts_app(client, appid)
            if page is None:
                return error_record(label, "not_tracked", f"steamcharts.com does not track appid {appid} (HTTP 404). "
                                    "Use mode 'appsCurrent' for its live count.", appid=appid)
            series = None
            if opt.include_series:
                raw = await client.get_json(f"{STEAMCHARTS}/app/{appid}/chart-data.json")
                if cutoff_ms:
                    raw = [p for p in raw if p[0] >= cutoff_ms]
                series = parse_chart_data(raw)
        except NotFound:
            return error_record(label, "not_tracked", f"steamcharts.com has no chart data for appid {appid}.", appid=appid)
        except Blocked as exc:
            return error_record(label, "blocked", str(exc), appid=appid)
        except UnexpectedShape as exc:
            return error_record(label, "unexpected_shape", str(exc), appid=appid)
        months = page.pop("months")
        if cutoff_ms:
            months = months[: max(1, opt.history_days // 30 + 2)]
        rec = envelope(label, "S1-steamcharts-app", "APP_HISTORY", appid=appid, **page,
                       steamchartsUrl=f"{STEAMCHARTS}/app/{appid}", months=months)
        rec["name"] = rec.get("name") or matched
        if series is not None:
            rec["series"] = series
            rec["seriesPoints"] = len(series)
        return rec

    for rec in await _bounded_map(apps, opt.concurrency, one):
        yield rec


async def steamcharts_top(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """steamcharts.com /top - the long tail (~12.7k games) ranked by current players."""
    pages_needed = -(-opt.max_items // STEAMCHARTS_TOP_PAGE_SIZE)
    emitted = 0
    page_no = 1
    while page_no <= pages_needed and emitted < opt.max_items:
        batch = list(range(page_no, min(pages_needed, page_no + opt.concurrency - 1) + 1))

        async def fetch(p: int) -> list[dict[str, Any]] | None:
            try:
                return parse_steamcharts_top(await client.get_text(f"{STEAMCHARTS}/top/p.{p}"))
            except NotFound:
                return None  # past the last page

        results = await _bounded_map(batch, opt.concurrency, fetch)
        for rows in results:
            if rows is None:
                return
            for row in rows:
                if emitted >= opt.max_items:
                    return
                if row["currentPlayers"] < opt.min_players:
                    # Sorted by current players: everything after this is smaller too.
                    return
                yield envelope("steamchartsTop", "S1-steamcharts-top", "STEAMCHARTS_TOP", **row,
                               steamchartsUrl=f"{STEAMCHARTS}/app/{row['appid']}")
                emitted += 1
            if len(rows) < STEAMCHARTS_TOP_PAGE_SIZE:
                return  # last page
        page_no = batch[-1] + 1


async def steam_online(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    """All of Steam: users logged in, last ~48h at ~5-minute resolution."""
    data = await client.get_json(URL_STEAM_ONLINE)
    if not isinstance(data, list) or not data:
        raise UnexpectedShape("userdata.json is not a non-empty list of series")
    for s in data:
        points = s.get("data") or []
        if not points:
            continue
        peak = max(points, key=lambda p: p[1])
        low = min(points, key=lambda p: p[1])
        rec = envelope("steamOnline", "S1-steam-store-stats", "STEAM_ONLINE",
                       label=s.get("label"), usersOnline=points[-1][1], usersOnlineAt=unix_to_iso(points[-1][0], ms=True),
                       peak48h=peak[1], peak48hAt=unix_to_iso(peak[0], ms=True),
                       low48h=low[1], low48hAt=unix_to_iso(low[0], ms=True))
        if opt.include_series:
            rec["series"] = [{"timestamp": unix_to_iso(t, ms=True), "users": v} for t, v in points]
            rec["seriesPoints"] = len(points)
        yield rec


MODES: dict[str, Callable[[SteamClient, Options], AsyncIterator[dict[str, Any]]]] = {
    "topConcurrent": top_concurrent,
    "topDailyPeak": top_daily_peak,
    "appsCurrent": apps_current,
    "appHistory": app_history,
    "steamchartsTop": steamcharts_top,
    "steamOnline": steam_online,
}
NEEDS_APPS = {"appsCurrent", "appHistory"}

# Which numeric field the change-detection layer compares between runs, per record type.
MONITORED_METRIC = {
    "TOP_CONCURRENT": "concurrent_in_game",
    "TOP_DAILY_PEAK": "peak_in_game",
    "APP_CURRENT": "player_count",
    "STEAMCHARTS_TOP": "currentPlayers",
    "STEAM_ONLINE": "usersOnline",
    "APP_HISTORY": "currentPlayers",
}
