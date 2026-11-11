"""One async generator per mode. Each yields finished records (envelope included)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable
from urllib.parse import urlparse

from .client import Blocked, NotFound, SteamClient
from .constants import (
    COMMUNITY,
    ITEM_ASSET_BASE,
    STORE_ITEMS_BATCH,
    URL_GAME_ACHIEVEMENTS,
    URL_PROFILE_ITEMS,
    URL_STORE_ITEMS,
)
from .parsers import (
    UnexpectedShape,
    ach_icon_url,
    envelope,
    error_record,
    html_error_message,
    parse_app_ref,
    parse_badges_html,
    parse_friends_html,
    parse_group_ref,
    parse_group_xml,
    parse_profile_html,
    parse_profile_ref,
    parse_profile_xml,
    parse_stats_xml,
    parse_xml,
    steam_ids,
    unix_to_iso,
)

log = logging.getLogger("steam.modes")


@dataclass
class Options:
    profiles: list[str] = field(default_factory=list)
    app_ids: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    max_items: int = 1000
    max_games_per_profile: int = 10
    include_profile_page: bool = True
    include_equipped_items: bool = False
    flatten_achievements: bool = False
    only_unlocked: bool = False
    enrich_profiles: bool = False
    language: str = "english"
    concurrency: int = 8


# --------------------------------------------------------------------------- helpers

async def bounded(items: Iterable[Any], fn: Callable[[Any], Awaitable[list[dict[str, Any]]]],
                  concurrency: int) -> AsyncIterator[dict[str, Any]]:
    """Run fn over items with bounded concurrency; yield records as each item finishes."""
    sem = asyncio.Semaphore(concurrency)

    async def run(item: Any) -> list[dict[str, Any]]:
        async with sem:
            try:
                return await fn(item)
            except UnexpectedShape as exc:
                log.error("%s: upstream layout changed - %s", item, exc)
                return [error_record(str(item), "unexpected_shape", str(exc))]
            except Blocked as exc:
                log.error("%s: blocked - %s", item, exc)
                return [error_record(str(item), "blocked", str(exc))]
            except NotFound as exc:
                return [error_record(str(item), "not_found", str(exc))]

    tasks = [asyncio.create_task(run(i)) for i in items]
    try:
        for fut in asyncio.as_completed(tasks):
            for rec in await fut:
                yield rec
    finally:
        for t in tasks:
            t.cancel()


class ProfileResolver:
    """Input reference -> parsed profile XML (cached). XML is never rate-limited."""

    def __init__(self, client: SteamClient) -> None:
        self.client = client
        self._cache: dict[str, Any] = {}
        self._html: dict[str, Any] = {}

    async def xml(self, ref: str) -> dict[str, Any]:
        """Return parsed profile, or raise _InputError."""
        parsed = parse_profile_ref(ref)
        if parsed is None:
            raise _InputError("invalid_input", f"Not a SteamID64, SteamID, profile URL or vanity name: {ref!r}")
        key = f"{parsed[0]}/{parsed[1].lower()}"
        if key not in self._cache:
            page = await self.client.get(f"{COMMUNITY}/{parsed[0]}/{parsed[1]}", {"xml": "1"})
            if not page.text.lstrip().startswith("<?xml"):
                raise UnexpectedShape(f"profile ?xml=1 returned non-XML ({len(page.text)} chars) at {page.url}")
            root = parse_xml(page.text)
            if root.tag == "response":
                # Unknown id/vanity: HTTP 200 + <response><error>, never a 404.
                err = root.findtext("error") or "unknown"
                self._cache[key] = _InputError("profile_not_found", err.strip())
            else:
                self._cache[key] = parse_profile_xml(root)
        val = self._cache[key]
        if isinstance(val, _InputError):
            raise val
        return val

    async def html(self, id64: str) -> dict[str, Any]:
        if id64 not in self._html:
            page = await self.client.get(f"{COMMUNITY}/profiles/{id64}/", html=True)
            self._html[id64] = parse_profile_html(page.text)
        return self._html[id64]


class _InputError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _identity(p: dict[str, Any]) -> dict[str, Any]:
    return {"steamId64": p["steamId64"], "personaName": p.get("personaName"), "profileUrl": p.get("profileUrl")}


def _item_urls(obj: Any) -> Any:
    """Make GetProfileItemsEquipped relative asset paths absolute, in place-copy."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and k.startswith(("image_", "movie_")) and v and not v.startswith("http"):
                out[k] = f"{ITEM_ASSET_BASE}/{v}"
            else:
                out[k] = _item_urls(v)
        return out
    return obj


# --------------------------------------------------------------------------- achievement schema

class AchievementSchema:
    """IPlayerService/GetGameAchievements (keyless): names, descriptions, hidden flag and
    global unlock % for every achievement, in the requested language. Cached per app."""

    def __init__(self, client: SteamClient, language: str) -> None:
        self.client = client
        self.language = language
        self._cache: dict[int, list[dict[str, Any]] | None] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    async def get(self, appid: int) -> list[dict[str, Any]] | None:
        lock = self._locks.setdefault(appid, asyncio.Lock())
        async with lock:
            if appid not in self._cache:
                data = await self.client.get_json(URL_GAME_ACHIEVEMENTS, {"appid": appid, "language": self.language})
                resp = data.get("response") if isinstance(data, dict) else None
                if resp is None:
                    raise UnexpectedShape(f"GetGameAchievements without 'response' for {appid}")
                # Unknown app and app-without-achievements both answer {"response":{}}.
                rows = resp.get("achievements")
                self._cache[appid] = [normalize_schema_row(appid, r) for r in rows] if rows else None
            return self._cache[appid]


def _pct(v: Any) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def normalize_schema_row(appid: int, r: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiname": r.get("internal_name"),
        "name": r.get("localized_name"),
        "description": r.get("localized_desc") or None,
        "hidden": bool(r.get("hidden")),
        "globalPercent": _pct(r.get("player_percent_unlocked")),
        "iconUrl": ach_icon_url(appid, r.get("icon")),
        "iconGrayUrl": ach_icon_url(appid, r.get("icon_gray")),
        "archived": bool(r.get("archived")),
        "progressType": r.get("progress_type"),
    }


def achievement_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pcts = [r["globalPercent"] for r in rows if r.get("globalPercent") is not None]
    rarest = min((r for r in rows if r.get("globalPercent") is not None), key=lambda r: r["globalPercent"], default=None)
    common = max((r for r in rows if r.get("globalPercent") is not None), key=lambda r: r["globalPercent"], default=None)
    return {
        "totalAchievements": len(rows),
        "hiddenAchievements": sum(1 for r in rows if r.get("hidden")),
        "averageGlobalPercent": round(sum(pcts) / len(pcts), 2) if pcts else None,
        "rarestAchievement": {"apiname": rarest["apiname"], "name": rarest["name"], "globalPercent": rarest["globalPercent"]} if rarest else None,
        "mostCommonAchievement": {"apiname": common["apiname"], "name": common["name"], "globalPercent": common["globalPercent"]} if common else None,
    }


async def store_names(client: SteamClient, appids: list[int], language: str) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for i in range(0, len(appids), STORE_ITEMS_BATCH):
        chunk = appids[i:i + STORE_ITEMS_BATCH]
        body = {"ids": [{"appid": a} for a in chunk], "context": {"language": language, "country_code": "US"}}
        try:
            data = await client.get_json(URL_STORE_ITEMS, {"input_json": json.dumps(body)})
        except (Blocked, NotFound) as exc:
            log.warning("Store name lookup failed for %d apps (%s) - continuing without names", len(chunk), exc)
            continue
        for item in (data.get("response") or {}).get("store_items") or []:
            if item.get("success") == 1 and item.get("appid"):
                out[int(item["appid"])] = item
    return out


# --------------------------------------------------------------------------- mode: profiles

async def mode_profiles(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    resolver = ProfileResolver(client)

    async def one(ref: str) -> list[dict[str, Any]]:
        try:
            p = await resolver.xml(ref)
        except _InputError as e:
            return [error_record(ref, e.kind, e.detail)]
        rec = envelope(ref, "S1-community-profile-xml", "PROFILE", **p)
        sources = ["S1-community-profile-xml"]
        # A non-public profile page carries nothing the XML lacks (no level, no
        # counts), so skip it - it spends the rate-limited HTML budget.
        if opt.include_profile_page and p["isPublic"]:
            try:
                h = await resolver.html(p["steamId64"])
                rec.update(
                    # The XML privacyState can lag the page: 1/168 'public' profiles in
                    # a cloud run rendered 'This profile is private.' (2026-10-11).
                    profilePagePrivate=h["pagePrivate"],
                    level=h["level"], counts=h["counts"], gameDetailsPublic=h["gameDetailsPublic"],
                    favoriteBadge=h["favoriteBadge"], statusHeader=h["statusHeader"], currentGame=h["currentGame"],
                    recentGames=h["recentGames"], showcaseStats=h["showcaseStats"], showcases=h["showcases"],
                )
                # The page's 'N hours past 2 weeks' covers every recent game; the XML
                # sum only the few listed in mostPlayedGames (59.2 vs 62.2 on recon).
                if h["hoursLast2WeeksHtml"] is not None:
                    rec["hoursPlayedLast2Weeks"] = h["hoursLast2WeeksHtml"]
                sources.append("S1-community-profile-html")
            except (Blocked, NotFound, UnexpectedShape) as exc:
                log.warning("%s: profile page enrichment failed (%s)", ref, exc)
                rec["profilePageError"] = str(exc)
        if opt.include_equipped_items:
            try:
                data = await client.get_json(URL_PROFILE_ITEMS, {"steamid": p["steamId64"], "language": opt.language})
                rec["equippedItems"] = _item_urls(data.get("response") or {})
                sources.append("S1-api-profile-items")
            except (Blocked, NotFound) as exc:
                rec["equippedItems"] = None
                log.warning("%s: equipped items lookup failed (%s)", ref, exc)
        rec["_source"] = "+".join(sources)
        return [rec]

    async for r in bounded(opt.profiles, one, opt.concurrency):
        yield r


# --------------------------------------------------------------------------- mode: userAchievements

_STATS_FRIENDLY: dict[int, str] = {}  # appid -> legacy stats name (440 -> TF2), learned from redirects


async def fetch_player_stats(client: SteamClient, id64: str, appid: int, stats_name: str | None) -> tuple[str, Any]:
    """-> ('ok', parsed) | ('private', None) | ('no_stats', detail) | ('error_page', message)."""
    path = stats_name or _STATS_FRIENDLY.get(appid) or str(appid)
    for _ in range(2):
        page = await client.get(f"{COMMUNITY}/profiles/{id64}/stats/{path}/", {"tab": "achievements", "xml": "1"})
        if page.text.lstrip().startswith("<?xml"):
            root = parse_xml(page.text)
            if root.tag == "response":
                return "error_page", root.findtext("error") or "XML error"
            parsed = parse_stats_xml(root)
            return ("private", parsed) if parsed["hidden"] else ("ok", parsed)
        final = urlparse(page.url).path.rstrip("/")
        m = re.search(r"/stats/([^/]+)$", final)
        if m and not m.group(1).isdigit() and m.group(1) != path:
            # Legacy Valve games redirect /stats/440/ -> /stats/TF2 and the redirect
            # DROPS ?xml=1, so the HTML page comes back. Retry on the friendly name.
            path = m.group(1)
            _STATS_FRIENDLY[appid] = path
            continue
        msg = html_error_message(page.text)
        if msg:
            return "error_page", msg
        if "/stats/" not in final:
            # App without Steam stats (or a bogus appid) redirects to the profile root.
            return "no_stats", "Steam redirected to the profile: this app has no Steam achievements/stats."
        return "error_page", f"Unexpected non-XML stats page at {page.url}"
    return "error_page", "stats redirect loop"


async def mode_user_achievements(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    resolver = ProfileResolver(client)
    schema = AchievementSchema(client, opt.language)
    explicit_apps = []
    bad_apps = []
    for a in opt.app_ids:
        aid = parse_app_ref(a)
        (explicit_apps if aid else bad_apps).append(aid or a)
    for b in bad_apps:
        yield error_record(str(b), "invalid_input", "Not an appid or Steam app URL.")

    async def one(ref: str) -> list[dict[str, Any]]:
        try:
            p = await resolver.xml(ref)
        except _InputError as e:
            return [error_record(ref, e.kind, e.detail)]
        ident = _identity(p)
        if not p["isPublic"]:
            return [error_record(ref, "profile_private", f"Profile privacy is '{p['privacyState']}' - achievements are not public.", **ident)]

        html: dict[str, Any] | None = None
        try:
            html = await resolver.html(p["steamId64"])
        except (Blocked, NotFound, UnexpectedShape) as exc:
            log.warning("%s: profile page unavailable (%s) - cannot verify game-details privacy", ref, exc)
        if html is not None and not html["gameDetailsPublic"]:
            return [error_record(ref, "game_details_private",
                                 "Profile is public but its game details are private. Steam would answer with every "
                                 "achievement locked, so no data is emitted rather than false zeros.", **ident)]

        known: dict[int, dict[str, Any]] = {}
        for g in p["recentGamesXml"]:
            if g["appid"]:
                known.setdefault(g["appid"], {}).update(statsName=g["statsName"], hoursLast2Weeks=g["hoursLast2Weeks"],
                                                        hoursOnRecord=g["hoursOnRecord"], name=g["name"])
        for g in (html or {}).get("recentGames") or []:
            if g["appid"]:
                k = known.setdefault(g["appid"], {})
                k.setdefault("name", g["name"])
                if k.get("hoursOnRecord") is None:
                    k["hoursOnRecord"] = g["hoursOnRecord"]
                k["lastPlayedDate"] = g["lastPlayedDate"]
        if explicit_apps:
            apps = list(dict.fromkeys(explicit_apps))
        else:
            apps = list(known)[: opt.max_games_per_profile]
            if not apps:
                return [error_record(ref, "no_recent_games",
                                     "No appIds given and the profile shows no recently played games "
                                     "(Steam's full owned-games list requires login). Pass appIds explicitly.", **ident)]

        out: list[dict[str, Any]] = []
        for appid in apps:
            out.extend(await _player_game(client, schema, opt, ref, p, ident, appid, known.get(appid) or {}, html))
        return out

    async for r in bounded(opt.profiles, one, opt.concurrency):
        yield r


async def _player_game(client: SteamClient, schema: AchievementSchema, opt: Options, ref: str, p: dict[str, Any],
                       ident: dict[str, Any], appid: int, known: dict[str, Any], html: dict[str, Any] | None) -> list[dict[str, Any]]:
    status, data = await fetch_player_stats(client, p["steamId64"], appid, known.get("statsName"))
    base = {**ident, "appid": appid}
    if status == "private":
        return [error_record(ref, "game_details_private", "Steam returned only the privacy state for this game.", **base)]
    if status == "no_stats":
        return [error_record(ref, "no_achievements", data, **base)]
    if status == "error_page":
        kind = "game_details_private" if "permission" in data.lower() else "stats_unavailable"
        return [error_record(ref, kind, data, **base)]

    try:
        rows = await schema.get(appid)
    except (Blocked, NotFound, UnexpectedShape) as exc:
        log.warning("appid %s: achievement schema unavailable (%s) - emitting without global %%", appid, exc)
        rows = None
    by_api = {r["apiname"].lower(): r for r in rows or [] if r.get("apiname")}

    achievements = []
    for a in data["achievements"]:
        # Stats XML says 'ach00' where the API says 'ACH00' - join case-insensitively.
        s = by_api.get((a["apiname"] or "").lower(), {})
        achievements.append({
            "apiname": s.get("apiname") or a["apiname"],
            "name": s.get("name") or a["name"],
            "description": s.get("description") or a["description"],
            "achieved": a["achieved"],
            "unlockTime": a["unlockTime"],
            "unlockedAt": unix_to_iso(a["unlockTime"]),
            "hidden": s.get("hidden"),
            "globalPercent": s.get("globalPercent"),
            "iconUrl": s.get("iconUrl") or a["iconClosed"],
            "iconGrayUrl": s.get("iconGrayUrl") or a["iconOpen"],
        })
    unlocked = [a for a in achievements if a["achieved"]]
    times = sorted(a["unlockTime"] for a in unlocked if a["unlockTime"])
    rarest = min((a for a in unlocked if a["globalPercent"] is not None), key=lambda a: a["globalPercent"], default=None)
    total = len(achievements)
    hours2w = data["hoursLast2Weeks"]
    in_recent = appid in {g["appid"] for g in p["recentGamesXml"]} or appid in {g["appid"] for g in (html or {}).get("recentGames") or []}
    summary = {
        **base,
        "gameName": data["gameName"],
        "gameLink": data["gameLink"],
        "gameIcon": data["gameIcon"],
        "gameLogo": data["gameLogo"],
        "statsName": data["gameFriendlyName"],
        "totalAchievements": total,
        "unlockedAchievements": len(unlocked),
        "completionPct": round(len(unlocked) / total * 100, 2) if total else None,
        "isPerfect": bool(total) and len(unlocked) == total,
        "firstUnlockAt": unix_to_iso(times[0]) if times else None,
        "lastUnlockAt": unix_to_iso(times[-1]) if times else None,
        "rarestUnlocked": {"apiname": rarest["apiname"], "name": rarest["name"], "globalPercent": rarest["globalPercent"]} if rarest else None,
        "hoursLast2Weeks": hours2w,
        "hoursOnRecord": known.get("hoursOnRecord"),
        "lastPlayedDate": known.get("lastPlayedDate"),
        # Steam answers this endpoint for ANY appid (owned or not) with every
        # achievement locked, so 0 unlocks + 0 recent hours cannot prove ownership.
        "ownershipConfirmed": bool(unlocked) or bool(hours2w) or in_recent,
        "gameDetailsPublic": html["gameDetailsPublic"] if html else None,
        "language": opt.language,
    }
    src = "S1-community-stats-xml" + ("+S1-api-game-achievements" if rows else "")
    if opt.flatten_achievements:
        return [envelope(ref, src, "PLAYER_ACHIEVEMENT", **{k: summary[k] for k in ("steamId64", "personaName", "profileUrl", "appid", "gameName")},
                         **a) for a in achievements if a["achieved"] or not opt.only_unlocked]
    return [envelope(ref, src, "PLAYER_GAME_ACHIEVEMENTS", **summary,
                     achievements=[a for a in achievements if a["achieved"] or not opt.only_unlocked])]


# --------------------------------------------------------------------------- mode: gameAchievements

async def mode_game_achievements(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    schema = AchievementSchema(client, opt.language)
    apps: list[tuple[str, int]] = []
    for a in opt.app_ids:
        aid = parse_app_ref(a)
        if aid is None:
            yield error_record(str(a), "invalid_input", "Not an appid or Steam app URL.")
        else:
            apps.append((str(a), aid))
    names = await store_names(client, list(dict.fromkeys(a for _, a in apps)), opt.language)

    async def one(item: tuple[str, int]) -> list[dict[str, Any]]:
        ref, appid = item
        rows = await schema.get(appid)
        store = names.get(appid) or {}
        if not rows:
            why = "App exists in the store but has no Steam achievements." if store else "Unknown appid (no store item, no achievements)."
            return [error_record(ref, "no_achievements", why, appid=appid, gameName=store.get("name"))]
        game = {"appid": appid, "gameName": store.get("name"),
                "storeUrl": f"https://store.steampowered.com/{store['store_url_path']}" if store.get("store_url_path") else None,
                "language": opt.language}
        src = "S1-api-game-achievements"
        ordered = sorted(rows, key=lambda r: -(r["globalPercent"] or 0))
        if opt.flatten_achievements:
            return [envelope(ref, src, "GAME_ACHIEVEMENT", **game, rank=i + 1, **r) for i, r in enumerate(ordered)]
        return [envelope(ref, src, "GAME_ACHIEVEMENTS", **game, **achievement_stats(rows), achievements=ordered)]

    async for r in bounded(apps, one, opt.concurrency):
        yield r


# --------------------------------------------------------------------------- mode: friends

async def mode_friends(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    resolver = ProfileResolver(client)

    async def one(ref: str) -> list[dict[str, Any]]:
        try:
            p = await resolver.xml(ref)
        except _InputError as e:
            return [error_record(ref, e.kind, e.detail)]
        owner = {"ownerSteamId64": p["steamId64"], "ownerPersonaName": p.get("personaName")}
        if not p["isPublic"]:
            return [error_record(ref, "profile_private", f"Profile privacy is '{p['privacyState']}'.", **owner)]
        page = await client.get(f"{COMMUNITY}/profiles/{p['steamId64']}/friends/", html=True)
        friends, meta = parse_friends_html(page.text)
        owner["ownerFriendCount"] = meta["friendCount"]
        if not friends:
            # A hidden list still renders the page ('Sorry, there are no players to
            # show.') - only the missing 'Friends' nav entry tells it apart.
            if not meta["listVisible"]:
                return [error_record(ref, "friends_private", "Friends list is hidden (private or friends-only).", **owner)]
            return [error_record(ref, "no_friends", "Friends list is public but empty.", **owner)]
        friends = friends[: opt.max_items]
        if opt.enrich_profiles:
            sub = ProfileResolver(client)

            async def enrich(f: dict[str, Any]) -> list[dict[str, Any]]:
                try:
                    x = await sub.xml(f["steamId64"])
                    f.update({k: x.get(k) for k in ("customURL", "privacyState", "vacBanned", "tradeBanState", "isLimitedAccount",
                                                     "memberSince", "memberSinceDate", "location", "realname", "avatarFull")})
                except _InputError:
                    pass
                return [f]
            friends = [r async for r in bounded(friends, enrich, 8)]
        return [envelope(ref, "S1-community-friends-html", "FRIEND", **owner, position=i + 1, **f) for i, f in enumerate(friends)]

    async for r in bounded(opt.profiles, one, opt.concurrency):
        yield r


# --------------------------------------------------------------------------- mode: badges

async def mode_badges(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    resolver = ProfileResolver(client)

    async def one(ref: str) -> list[dict[str, Any]]:
        try:
            p = await resolver.xml(ref)
        except _InputError as e:
            return [error_record(ref, e.kind, e.detail)]
        owner = {"ownerSteamId64": p["steamId64"], "ownerPersonaName": p.get("personaName")}
        if not p["isPublic"]:
            return [error_record(ref, "profile_private", f"Profile privacy is '{p['privacyState']}'.", **owner)]
        out: list[dict[str, Any]] = []
        page_no = 1
        while len(out) < opt.max_items:
            page = await client.get(f"{COMMUNITY}/profiles/{p['steamId64']}/badges/", {"p": page_no} if page_no > 1 else None, html=True)
            data = parse_badges_html(page.text)
            if not data["badges"]:
                if page_no == 1:
                    kind = "badges_private" if data["privateMessage"] else "no_badges"
                    return [error_record(ref, kind, data["privateMessage"] or "No badges shown on the badges page.", **owner)]
                break
            meta = {**owner, "profileLevel": data["level"], "profileXp": data["xp"], "xpToNextLevel": data["xpToNextLevel"],
                    "totalBadges": data["totalBadges"] or None}
            for b in data["badges"]:
                out.append(envelope(ref, "S1-community-badges-html", "BADGE", **meta, page=page_no, **b))
            # Pager: 'Showing 1-150 of 6,506 badges'; absent when everything fits on one page.
            if not data["totalBadges"] or (data["showingTo"] or 0) >= data["totalBadges"]:
                break
            page_no += 1
        if out and out[0]["totalBadges"] is None:
            for r in out:
                r["totalBadges"] = len(out)
        return out[: opt.max_items]

    async for r in bounded(opt.profiles, one, opt.concurrency):
        yield r


# --------------------------------------------------------------------------- mode: groupMembers

async def mode_group_members(client: SteamClient, opt: Options) -> AsyncIterator[dict[str, Any]]:
    resolver = ProfileResolver(client)
    for ref in opt.groups:
        g = parse_group_ref(ref)
        if g is None:
            yield error_record(ref, "invalid_input", "Not a Steam group URL, group vanity name or 18-digit group id.")
            continue
        emitted = 0
        page_no = 1
        while emitted < opt.max_items:
            try:
                page = await client.get(f"{COMMUNITY}/{g[0]}/{g[1]}/memberslistxml/", {"xml": "1", "p": page_no})
            except (Blocked, NotFound) as exc:
                yield error_record(ref, "blocked" if isinstance(exc, Blocked) else "group_not_found", str(exc))
                break
            if not page.text.lstrip().startswith("<?xml"):
                yield error_record(ref, "group_not_found", html_error_message(page.text) or f"Non-XML member list at {page.url}")
                break
            root = parse_xml(page.text)
            if root.tag == "response":
                yield error_record(ref, "group_not_found", (root.findtext("error") or "").strip())
                break
            data = parse_group_xml(root)
            group = {k: data[k] for k in ("groupId64", "groupName", "groupUrl", "memberCount", "membersOnline", "membersInGame")}
            ids = data["members"][: opt.max_items - emitted]
            if not ids:
                break
            if opt.enrich_profiles:
                async def enrich(sid: str) -> list[dict[str, Any]]:
                    try:
                        x = await resolver.xml(sid)
                        keep = ("personaName", "customURL", "profileUrl", "privacyState", "onlineState", "vacBanned",
                                "tradeBanState", "isLimitedAccount", "memberSince", "memberSinceDate", "location",
                                "realname", "avatarFull", "hoursPlayedLast2Weeks")
                        return [{**steam_ids(int(sid)), **{k: x.get(k) for k in keep}}]
                    except _InputError as e:
                        return [{**steam_ids(int(sid)), "profileError": e.detail}]
                rows = [r async for r in bounded(ids, enrich, opt.concurrency)]
            else:
                rows = [{**steam_ids(int(s)), "profileUrl": f"{COMMUNITY}/profiles/{s}/"} for s in ids]
            for r in rows:
                emitted += 1
                yield envelope(ref, "S1-community-group-xml", "GROUP_MEMBER", **group, page=page_no, **r)
            if not data["nextPageLink"] or page_no >= (data["totalPages"] or page_no):
                break
            page_no += 1


MODES: dict[str, Callable[[SteamClient, Options], AsyncIterator[dict[str, Any]]]] = {
    "profiles": mode_profiles,
    "userAchievements": mode_user_achievements,
    "gameAchievements": mode_game_achievements,
    "friends": mode_friends,
    "badges": mode_badges,
    "groupMembers": mode_group_members,
}
NEEDS_PROFILES = {"profiles", "userAchievements", "friends", "badges"}
NEEDS_APPS = {"gameAchievements"}
NEEDS_GROUPS = {"groupMembers"}
