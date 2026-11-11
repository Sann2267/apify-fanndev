"""Pure parsing: upstream payloads -> records. No I/O here."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from selectolax.parser import HTMLParser, Node

from .constants import ACH_ICON_BASE, COMMUNITY, STEAMID64_BASE


class UnexpectedShape(Exception):
    """Upstream changed its layout. Raised instead of emitting hollow records."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_iso(ts: Any) -> str | None:
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str, **payload: Any) -> dict[str, Any]:
    return {"_input": input_value, "_source": source, "_scrapedAt": utc_now_iso(), "recordType": record_type, **payload}


def error_record(input_value: str, kind: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {"_input": input_value, "_source": "none", "_scrapedAt": utc_now_iso(), "recordType": "ERROR",
            "_error": kind, "_errorDetail": detail, **extra}


def _int(s: Any) -> int | None:
    if s is None:
        return None
    m = re.search(r"-?[\d,]+", str(s))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _float(s: Any) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?[\d,]*\.?\d+", str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    t = " ".join(node.text(separator=" ").split())
    return t or None


# --------------------------------------------------------------------------- Steam IDs

_STEAM2 = re.compile(r"^STEAM_[0-5]:([01]):(\d+)$", re.I)
_STEAM3 = re.compile(r"^\[?U:1:(\d+)\]?$", re.I)
_VANITY = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


def steam_ids(id64: int) -> dict[str, Any]:
    account = id64 - STEAMID64_BASE
    return {
        "steamId64": str(id64),
        "accountId": account,
        "steamId2": f"STEAM_1:{account & 1}:{account >> 1}",
        "steamId3": f"[U:1:{account}]",
    }


def parse_profile_ref(value: Any) -> tuple[str, str] | None:
    """Turn any profile reference into ('profiles', id64) or ('id', vanity).

    Accepts SteamID64, profile/vanity URLs, STEAM_X:Y:Z, [U:1:N], a 32-bit
    account id and bare vanity names. Returns None for anything unusable.
    """
    s = str(value or "").strip()
    if not s:
        return None
    if s.lower().startswith(("http://", "https://", "steamcommunity.com", "www.steamcommunity.com")):
        u = urlparse(s if "://" in s else "https://" + s)
        if not u.netloc.lower().endswith("steamcommunity.com"):
            return None
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "profiles" and parts[1].isdigit():
            return ("profiles", parts[1])
        if len(parts) >= 2 and parts[0] == "id":
            return ("id", unquote(parts[1]))
        return None
    if s.isdigit():
        n = int(s)
        if n > STEAMID64_BASE:
            return ("profiles", str(n))
        if 0 < n < 2 ** 32:
            return ("profiles", str(STEAMID64_BASE + n))
        return None
    m = _STEAM2.match(s)
    if m:
        return ("profiles", str(STEAMID64_BASE + int(m.group(2)) * 2 + int(m.group(1))))
    m = _STEAM3.match(s)
    if m:
        return ("profiles", str(STEAMID64_BASE + int(m.group(1))))
    if _VANITY.match(s):
        return ("id", s)
    return None


def profile_base(kind: str, ident: str) -> str:
    return f"{COMMUNITY}/{kind}/{ident}"


_APP_URL = re.compile(r"(?:store\.steampowered\.com|steamcommunity\.com|steamdb\.info|steamcharts\.com)/(?:app|stats)/(\d+)", re.I)


def parse_app_ref(value: Any) -> int | None:
    s = str(value or "").strip()
    if s.isdigit():
        return int(s) or None
    m = _APP_URL.search(s)
    return int(m.group(1)) if m else None


_GROUP_URL = re.compile(r"steamcommunity\.com/(groups|gid)/([^/?#]+)", re.I)


def parse_group_ref(value: Any) -> tuple[str, str] | None:
    s = str(value or "").strip()
    if not s:
        return None
    m = _GROUP_URL.search(s)
    if m:
        return (m.group(1).lower(), unquote(m.group(2)))
    if s.isdigit() and len(s) == 18:
        return ("gid", s)
    if _VANITY.match(s):
        return ("groups", s)
    return None


# --------------------------------------------------------------------------- dates

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def parse_community_date(text: str | None, *, today: datetime | None = None) -> str | None:
    """'September 12, 2003' / '26 April, 2025' / '9 Nov, 2015 @ 5:17pm' / '10 Oct' -> 'YYYY-MM-DD'.

    Steam omits the year when it is the current year. Time-of-day is dropped:
    anonymous pages render it in an unstated server time zone.
    """
    if not text:
        return None
    t = text.split("@")[0].strip().rstrip(".")
    day = month = year = None
    m = re.search(r"([A-Za-z]{3,})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", t)  # Month D, YYYY
    m2 = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s*(\d{4})?", t)  # D Month, YYYY
    if m2 and m2.group(2)[:3].lower() in _MONTHS:
        day, month, year = int(m2.group(1)), _MONTHS[m2.group(2)[:3].lower()], m2.group(3)
    elif m and m.group(1)[:3].lower() in _MONTHS:
        day, month, year = int(m.group(2)), _MONTHS[m.group(1)[:3].lower()], m.group(3)
    else:
        return None
    if year is None:
        now = today or datetime.now(timezone.utc)
        year = now.year
        try:
            if datetime(year, month, day, tzinfo=timezone.utc) > now:  # Dec date seen in Jan
                year -= 1
        except ValueError:
            return None
    try:
        return datetime(int(year), month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


# --------------------------------------------------------------------------- XML

_BAD_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_xml(text: str) -> ET.Element:
    return ET.fromstring(_BAD_XML_CHARS.sub("", text).encode("utf8"))


def _x(el: ET.Element | None, tag: str) -> str | None:
    if el is None:
        return None
    c = el.find(tag)
    if c is None or c.text is None:
        return None
    v = c.text.strip()
    return v or None


def _strip_html(s: str | None) -> str | None:
    if not s:
        return None
    t = HTMLParser(s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")).text(separator="")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t).strip()
    return t or None


def xml_error(root: ET.Element) -> str | None:
    if root.tag == "response":
        return _x(root, "error") or "unknown XML error"
    return None


def parse_profile_xml(root: ET.Element) -> dict[str, Any]:
    if root.tag != "profile" or _x(root, "steamID64") is None:
        raise UnexpectedShape(f"profile XML root <{root.tag}> without steamID64")
    id64 = int(_x(root, "steamID64"))
    custom = _x(root, "customURL")
    most: list[dict[str, Any]] = []
    for g in root.findall("./mostPlayedGames/mostPlayedGame"):
        link = _x(g, "gameLink") or ""
        appm = re.search(r"/app/(\d+)", link)
        most.append({
            "appid": int(appm.group(1)) if appm else None,
            "name": _x(g, "gameName"),
            "statsName": _x(g, "statsName"),
            "hoursLast2Weeks": _float(_x(g, "hoursPlayed")),
            "hoursOnRecord": _float(_x(g, "hoursOnRecord")),
            "gameLink": link or None,
            "gameIcon": _x(g, "gameIcon"),
            "gameLogo": _x(g, "gameLogo"),
        })
    groups: list[dict[str, Any]] = []
    for g in root.findall("./groups/group"):
        rec: dict[str, Any] = {"groupId64": _x(g, "groupID64"), "isPrimary": g.get("isPrimary") == "1"}
        if _x(g, "groupName") is not None:  # only the first few groups carry details
            rec.update(name=_x(g, "groupName"), groupUrl=f"{COMMUNITY}/groups/{_x(g, 'groupURL')}" if _x(g, "groupURL") else None,
                       headline=_x(g, "headline"), avatarFull=_x(g, "avatarFull"),
                       memberCount=_int(_x(g, "memberCount")), membersOnline=_int(_x(g, "membersOnline")),
                       membersInGame=_int(_x(g, "membersInGame")), membersInChat=_int(_x(g, "membersInChat")))
        groups.append(rec)
    summary_html = _x(root, "summary")
    member_since = _x(root, "memberSince")
    privacy = _x(root, "privacyState")
    rec = {
        **steam_ids(id64),
        "personaName": _x(root, "steamID"),
        "customURL": custom,
        "profileUrl": f"{COMMUNITY}/id/{custom}/" if custom else f"{COMMUNITY}/profiles/{id64}/",
        "privacyState": privacy,
        "visibilityState": _int(_x(root, "visibilityState")),
        "isPublic": privacy == "public",
        "onlineState": _x(root, "onlineState"),
        "stateMessage": _strip_html(_x(root, "stateMessage")),
        "avatarIcon": _x(root, "avatarIcon"),
        "avatarMedium": _x(root, "avatarMedium"),
        "avatarFull": _x(root, "avatarFull"),
        "vacBanned": _x(root, "vacBanned") == "1",
        "tradeBanState": _x(root, "tradeBanState"),
        "isLimitedAccount": _x(root, "isLimitedAccount") == "1",
        "memberSince": member_since,
        "memberSinceDate": parse_community_date(member_since),
        "realname": _x(root, "realname"),
        "location": _x(root, "location"),
        "headline": _x(root, "headline"),
        "summary": _strip_html(summary_html),
        "summaryHtml": summary_html,
        # <hoursPlayed2Wk> reads 0.0 even when mostPlayedGames carries 29.8 h
        # (recon 2026-10-11), so the real figure is the sum of the recent games.
        "hoursPlayedLast2Weeks": round(sum(g["hoursLast2Weeks"] or 0 for g in most), 1) if most else None,
        "recentGamesXml": most,
        "groups": groups,
        "groupCount": len(groups) if privacy == "public" else None,
    }
    return rec


def parse_stats_xml(root: ET.Element) -> dict[str, Any]:
    """Player achievement XML. Returns privacy-only dict when stats are hidden."""
    if root.tag != "playerstats":
        raise UnexpectedShape(f"stats XML root <{root.tag}>")
    privacy = _x(root, "privacyState")
    game = root.find("game")
    if game is None:
        return {"privacyState": privacy, "hidden": True}
    achievements = []
    for a in root.findall("./achievements/achievement"):
        ts = _int(_x(a, "unlockTimestamp"))
        achievements.append({
            "apiname": _x(a, "apiname"),
            "name": _x(a, "name"),
            "description": _x(a, "description"),
            "achieved": a.get("closed") == "1",
            "unlockTime": ts,
            "iconClosed": _x(a, "iconClosed"),
            "iconOpen": _x(a, "iconOpen"),
        })
    player = root.find("player")
    return {
        "privacyState": privacy,
        "hidden": False,
        "gameName": _x(game, "gameName"),
        "gameFriendlyName": _x(game, "gameFriendlyName"),
        "gameLink": _x(game, "gameLink"),
        "gameIcon": _x(game, "gameIcon"),
        "gameLogo": _x(game, "gameLogo"),
        "steamId64": _x(player, "steamID64"),
        "customURL": _x(player, "customURL"),
        # This is LAST-2-WEEKS playtime, not lifetime: it matched the review API's
        # playtime_last_two_weeks on every non-zero sample (recon 2026-10-11).
        "hoursLast2Weeks": _float(_x(root.find("stats"), "hoursPlayed")),
        "achievements": achievements,
    }


def parse_group_xml(root: ET.Element) -> dict[str, Any]:
    if root.tag != "memberList":
        raise UnexpectedShape(f"group XML root <{root.tag}>")
    d = root.find("groupDetails")
    url = _x(d, "groupURL")
    return {
        "groupId64": _x(root, "groupID64"),
        "groupName": _x(d, "groupName"),
        "groupUrl": f"{COMMUNITY}/groups/{url}" if url else None,
        "headline": _x(d, "headline"),
        "avatarFull": _x(d, "avatarFull"),
        "memberCount": _int(_x(root, "memberCount")),
        "membersOnline": _int(_x(d, "membersOnline")),
        "membersInGame": _int(_x(d, "membersInGame")),
        "membersInChat": _int(_x(d, "membersInChat")),
        "totalPages": _int(_x(root, "totalPages")),
        "currentPage": _int(_x(root, "currentPage")),
        "nextPageLink": _x(root, "nextPageLink"),
        "members": [m.text.strip() for m in root.findall("./members/steamID64") if m.text],
    }


# --------------------------------------------------------------------------- HTML

def html_error_message(html: str) -> str | None:
    """Steam's generic error page ('Steam Community :: Error') -> its message."""
    if "<title>Steam Community :: Error</title>" not in html:
        return None
    tree = HTMLParser(html)
    for sel in ("#message h3", ".error_ctn h3", "#message", ".profile_fatalerror_message", "h3"):
        t = _text(tree.css_first(sel))
        if t:
            return t
    return "Steam error page"


_COUNT_KEYS = {
    "badges": "badges", "games": "games", "inventory": "inventory", "screenshots": "screenshots",
    "videos": "videos", "workshop items": "workshopItems", "reviews": "reviews", "guides": "guides",
    "artwork": "artwork", "groups": "groups", "friends": "friends", "recommended": "reviews",
}


def parse_profile_html(html: str) -> dict[str, Any]:
    tree = HTMLParser(html)
    if tree.css_first(".profile_page") is None and tree.css_first(".profile_header") is None:
        raise UnexpectedShape("profile page without .profile_header")
    out: dict[str, Any] = {}
    # A private page carries class 'private_profile' on .profile_page; the
    # .profile_private_info box can be EMPTY (seen while the XML still said
    # privacyState=public), so the class is the marker, not the message.
    private = tree.css_first(".profile_page.private_profile") is not None
    msg = _text(tree.css_first(".profile_private_info"))
    private = private or msg is not None
    out["pagePrivate"] = private
    out["privateMessage"] = msg
    lvl = tree.css_first(".persona_level .friendPlayerLevelNum")
    out["level"] = _int(_text(lvl))

    counts: dict[str, int | None] = {}
    for link in tree.css(".profile_count_link"):
        label = (_text(link.css_first(".count_link_label")) or "").lower()
        key = _COUNT_KEYS.get(label)
        if key:
            counts[key] = _int(_text(link.css_first(".profile_count_link_total")))
    out["counts"] = counts
    # 'Games' count link exists only when game details are public. With hidden
    # game details the stats XML still answers 200 with every achievement
    # locked (hollow), so this flag is what tells the two apart.
    out["gameDetailsPublic"] = "games" in counts and not private

    fav = tree.css_first(".favorite_badge")
    if fav is not None:
        href = fav.attributes.get("href") or ""
        out["favoriteBadge"] = {
            "name": _text(fav.css_first(".favorite_badge_description .name")),
            "xp": _int(_text(fav.css_first(".favorite_badge_description .xp"))),
            "tooltip": (fav.css_first(".favorite_badge_icon").attributes.get("data-tooltip-html") or "").replace("<br>", " | ").strip()
            if fav.css_first(".favorite_badge_icon") else None,
            "badgeUrl": href or None,
            "appid": _int(re.search(r"/gamecards/(\d+)", href).group(1)) if "/gamecards/" in href else None,
        }
    else:
        out["favoriteBadge"] = None

    status = tree.css_first(".profile_in_game")
    out["statusHeader"] = _text(status.css_first(".profile_in_game_header")) if status else None
    out["currentGame"] = _text(status.css_first(".profile_in_game_name")) if status else None

    hdr = tree.css_first(".recentgame_quicklinks")
    out["hoursLast2WeeksHtml"] = _float(_text(hdr)) if hdr and "past 2 weeks" in (_text(hdr) or "") else None
    recent = []
    for g in tree.css(".recent_game"):
        name_a = g.css_first(".game_name a")
        href = name_a.attributes.get("href") if name_a else ""
        details = _text(g.css_first(".game_info_details")) or ""
        prog = _text(g.css_first(".game_info_achievement_summary .ellipsis"))
        pm = re.match(r"([\d,]+)\s+of\s+([\d,]+)", prog or "")
        last = re.search(r"last played on (.+)$", details)
        recent.append({
            "appid": _int(re.search(r"/app/(\d+)", href or "").group(1)) if href and "/app/" in href else None,
            "name": _text(name_a),
            "hoursOnRecord": _float(details.split("hrs on record")[0]) if "hrs on record" in details else None,
            "lastPlayed": last.group(1).strip() if last else None,
            "lastPlayedDate": parse_community_date(last.group(1)) if last else None,
            "currentlyInGame": "Currently In-Game" in details,
            "achievementsUnlocked": _int(pm.group(1)) if pm else None,
            "achievementsTotal": _int(pm.group(2)) if pm else None,
        })
    out["recentGames"] = recent

    showcase: dict[str, Any] = {}
    for row in tree.css(".showcase_stats_row .showcase_stat"):
        label = _text(row.css_first(".label"))
        value = _text(row.css_first(".value"))
        if label:
            showcase[label] = _float(value) if value and re.search(r"\d", value) else value
    out["showcaseStats"] = showcase or None
    out["showcases"] = [t for t in (_text(n) for n in tree.css(".profile_customization_header")) if t and not t.startswith("Recent Activity")] or None
    return out


def parse_friends_html(html: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """-> (friends, {friendCount, listVisible})."""
    tree = HTMLParser(html)
    if tree.css_first(".friends_nav") is None and tree.css_first("#friends_list") is None:
        raise UnexpectedShape("friends page without .friends_nav / #friends_list")
    counts = re.search(r"g_rgCounts\s*=\s*(\{[^;]*?\})\s*;", html)
    cfriends = None
    if counts:
        m = re.search(r'"cFriends"\s*:\s*(\d+)', counts.group(1))
        cfriends = int(m.group(1)) if m else None
    # The 'All Friends' nav link (data-navid="friends") is rendered only when the list is visible.
    meta = {"friendCount": cfriends, "listVisible": tree.css_first('.friends_nav a[data-navid="friends"]') is not None}
    out = []
    for b in tree.css(".friend_block_v2"):
        sid = b.attributes.get("data-steamid")
        if not sid:
            continue
        a = b.css_first("a.selectable_overlay")
        content = b.css_first(".friend_block_content")
        small = _text(content.css_first(".friend_small_text")) if content else None
        name = None
        if content is not None:
            first = content.child
            name = (first.text_content or "").strip() if first is not None and first.tag == "-text" else None
            if not name:
                name = (_text(content) or "").replace(small or "", "").strip() or None
        classes = (b.attributes.get("class") or "").split()
        state = next((c for c in ("in-game", "online", "offline") if c in classes), None)
        img = b.css_first(".player_avatar img")
        out.append({
            **steam_ids(int(sid)),
            "personaName": name,
            "profileUrl": (a.attributes.get("href") if a else None) or f"{COMMUNITY}/profiles/{sid}",
            "onlineState": state,
            "statusText": small,
            "avatarMedium": img.attributes.get("src") if img else None,
        })
    return out, meta


def parse_badges_html(html: str) -> dict[str, Any]:
    tree = HTMLParser(html)
    xp_block = _text(tree.css_first(".profile_xp_block"))
    showing = re.search(r"Showing\s+([\d,]+)\s*-\s*([\d,]+)\s+of\s+([\d,]+)", html)
    badges = []
    for row in tree.css(".badge_row"):
        rid = (row.attributes.get("id") or "")
        overlay = row.css_first("a.badge_row_overlay")
        href = overlay.attributes.get("href") if overlay else None
        title_node = row.css_first(".badge_title")
        title = _text(title_node)
        if title:
            title = title.replace("View details", "").strip()
        info = row.css_first(".badge_info_description")
        lvl_xp = None
        if info is not None:
            for div in info.css("div"):
                t = _text(div)
                if t and "XP" in t and "badge_info" not in (div.attributes.get("class") or ""):
                    lvl_xp = t
                    break
        unlocked = _text(row.css_first(".badge_info_unlocked"))
        unlocked = unlocked.replace("Unlocked", "", 1).strip() if unlocked else None
        img = row.css_first(".badge_info_image img")
        gm = re.match(r"badge_gamebadge_(\d+)_(\d+)", rid)
        lm = re.search(r"Level\s+([\d,]+)", lvl_xp or "")
        xm = re.search(r"([\d,]+)\s*XP", lvl_xp or "")
        progress = _text(row.css_first(".badge_progress_info"))
        drops = _text(row.css_first(".badge_title_stats_drops"))
        playtime = _text(row.css_first(".badge_title_stats_playtime"))
        badges.append({
            "badgeKey": rid.replace("badge_", "", 1) or None,
            "badgeType": "game" if gm else "community",
            "appid": int(gm.group(1)) if gm else None,
            "isFoil": (gm.group(2) == "1") if gm else None,
            "badgeId": _int(re.search(r"/badges/(\d+)", href or "").group(1)) if href and re.search(r"/badges/(\d+)", href) else None,
            "title": title,
            "levelName": _text(row.css_first(".badge_info_title")),
            "level": _int(lm.group(1)) if lm else None,
            "xp": _int(xm.group(1)) if xm else None,
            "unlocked": unlocked,
            "unlockedDate": parse_community_date(unlocked),
            "isEarned": unlocked is not None,
            "progress": progress,
            "cardDrops": drops,
            "playtime": playtime,
            "iconUrl": (img.attributes.get("data-delayed-image") or img.attributes.get("src")) if img else None,
            "badgeUrl": href,
        })
    lvl = re.search(r"Level\s+([\d,]+)", xp_block or "")
    xp = re.search(r"XP\s+([\d,]+)", xp_block or "")
    nxt = re.search(r"([\d,]+)\s+XP to reach Level", xp_block or "")
    return {
        "level": _int(lvl.group(1)) if lvl else None,
        "xp": _int(xp.group(1)) if xp else None,
        "xpToNextLevel": _int(nxt.group(1)) if nxt else None,
        "showingFrom": _int(showing.group(1)) if showing else None,
        "showingTo": _int(showing.group(2)) if showing else None,
        "totalBadges": _int(showing.group(3)) if showing else None,
        "badges": badges,
        "privateMessage": _text(tree.css_first(".profile_private_info")),
    }


def ach_icon_url(appid: int, file: str | None) -> str | None:
    return f"{ACH_ICON_BASE}/{appid}/{file}" if file else None
