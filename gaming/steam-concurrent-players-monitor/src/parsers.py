"""Pure parsing: upstream payloads -> records. No I/O here."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any


class UnexpectedShape(Exception):
    """Upstream changed its layout. Raised instead of emitting hollow records."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_iso(ts: int | float | None, *, ms: bool = False) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts / 1000 if ms else ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str, **payload: Any) -> dict[str, Any]:
    return {"_input": input_value, "_source": source, "_scrapedAt": utc_now_iso(), "recordType": record_type, **payload}


def error_record(input_value: str, kind: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": kind,
        "_errorDetail": detail,
        **extra,
    }


# --------------------------------------------------------------------------- input resolution

_APP_URL = re.compile(r"(?:store\.steampowered\.com|steamcharts\.com|steamdb\.info|steamcommunity\.com)/app/(\d+)", re.I)


def parse_app_ref(value: Any) -> tuple[int | None, str | None]:
    """Return (appid, None) for ids/URLs, or (None, search_term) for a game name."""
    if isinstance(value, int):
        return (value, None) if value > 0 else (None, None)
    s = str(value or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        return int(s), None
    m = _APP_URL.search(s)
    if m:
        return int(m.group(1)), None
    if s.lower().startswith(("http://", "https://")):
        return None, None  # a URL we cannot read an appid from - not a name either
    return None, s


def store_item_summary(item: dict[str, Any] | None) -> dict[str, Any]:
    """Flat convenience fields from an IStoreBrowseService item (item itself is kept verbatim)."""
    if not item or item.get("success") != 1:
        return {"name": (item or {}).get("name") or None}
    basic = item.get("basic_info") or {}
    release = item.get("release") or {}
    return {
        "name": item.get("name"),
        "storeUrl": f"https://store.steampowered.com/{item['store_url_path']}" if item.get("store_url_path") else None,
        "isFree": bool(item.get("is_free", False)),  # protobuf-JSON omits false fields
        "developers": [d.get("name") for d in basic.get("developers") or [] if d.get("name")],
        "publishers": [p.get("name") for p in basic.get("publishers") or [] if p.get("name")],
        "releaseDate": unix_to_iso(release.get("steam_release_date")),
    }


# --------------------------------------------------------------------------- steamcharts.com

_TITLE = re.compile(r"<title>\s*(.*?)\s*-\s*Steam Charts\s*</title>", re.S)
_STAT = re.compile(r'<div class="app-stat">\s*<span class="num">([\d,]+)</span>\s*<br>\s*(.*?)</div>', re.S)
_TIMEAGO = re.compile(r'class="timeago" title="([^"]+)"')
_TABLE = re.compile(r'<table class="common-table">(.*?)</table>', re.S)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _cell_text(raw: str) -> str:
    return html.unescape(_TAG.sub("", raw)).strip()


def _num(text: str, cast: type = int) -> int | float | None:
    t = text.replace(",", "").replace("%", "").strip()
    if t in ("", "-"):
        return None
    try:
        return cast(t)
    except ValueError:
        return None


def parse_steamcharts_app(page: str) -> dict[str, Any]:
    """App page -> current/24h/all-time stats and the full monthly table."""
    m = _TITLE.search(page)
    name = html.unescape(m.group(1)) if m else None

    stats: dict[str, Any] = {}
    for num, label in _STAT.findall(page):
        value = int(num.replace(",", ""))
        lab = _TAG.sub("", label).strip().lower()
        if lab.startswith("playing"):
            stats["currentPlayers"] = value
            t = _TIMEAGO.search(label)
            stats["currentPlayersAt"] = t.group(1) if t else None
        elif "24-hour" in lab:
            stats["peak24h"] = value
        elif "all-time" in lab:
            stats["allTimePeak"] = value
    if "currentPlayers" not in stats or "allTimePeak" not in stats:
        raise UnexpectedShape("steamcharts app page: app-stat blocks not found")

    t = _TABLE.search(page)
    if not t:
        raise UnexpectedShape("steamcharts app page: monthly table not found")
    months: list[dict[str, Any]] = []
    for row in _ROW.findall(t.group(1)):
        cells = [_cell_text(c) for c in _CELL.findall(row)]
        if len(cells) != 5:
            continue  # header row
        months.append({
            "month": cells[0],
            "avgPlayers": _num(cells[1], float),
            "gain": _num(cells[2], float),
            "gainPct": _num(cells[3], float),
            "peakPlayers": _num(cells[4]),
        })
    if not months:
        raise UnexpectedShape("steamcharts app page: monthly table has no rows")
    return {"name": name, **stats, "months": months}


def parse_chart_data(data: Any) -> list[dict[str, Any]]:
    """chart-data.json [[ms, players], ...] -> [{timestamp, players, resolution}].

    Resolution on 2026-10-11: monthly up to 2026-06, daily 2026-07-13..09-10,
    hourly for the last ~30 days. Derived from the gap to the next point.
    """
    if not isinstance(data, list) or (data and not (isinstance(data[0], list) and len(data[0]) == 2)):
        raise UnexpectedShape("chart-data.json is not a list of [ms, players] pairs")
    out = []
    for i, (ms, players) in enumerate(data):
        gap_h = ((data[i + 1][0] - ms) / 3_600_000) if i + 1 < len(data) else ((ms - data[i - 1][0]) / 3_600_000 if i else 0)
        res = "hourly" if gap_h <= 3 else "daily" if gap_h <= 48 else "monthly"
        out.append({"timestamp": unix_to_iso(ms, ms=True), "players": players, "resolution": res})
    return out


_TOP_TABLE = re.compile(r'<table id="top-games"[^>]*>(.*?)</table>', re.S)
_TOP_ROW = re.compile(
    r'<td>\s*(\d+)\.\s*</td>\s*<td class="game-name[^"]*">\s*<a href="/app/(\d+)">\s*(.*?)\s*</a>\s*</td>'
    r'\s*<td class="num">\s*([\d,]+)\s*</td>.*?peak-concurrent">\s*([\d,]+)\s*</td>'
    r'\s*<td class="num period-col player-hours">\s*([\d,]+)\s*</td>',
    re.S,
)


def parse_steamcharts_top(page: str) -> list[dict[str, Any]]:
    t = _TOP_TABLE.search(page)
    if not t:
        raise UnexpectedShape("steamcharts /top: #top-games table not found")
    rows = []
    for rank, appid, name, cur, peak, hours in _TOP_ROW.findall(t.group(1)):
        rows.append({
            "rank": int(rank),
            "appid": int(appid),
            "name": html.unescape(name).strip(),
            "currentPlayers": int(cur.replace(",", "")),
            "peakPlayers30d": int(peak.replace(",", "")),
            "hoursPlayed30d": int(hours.replace(",", "")),
        })
    if not rows and "<tbody>" in t.group(1) and "<td" in t.group(1):
        raise UnexpectedShape("steamcharts /top: table has cells but no row matched")
    return rows
