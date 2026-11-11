"""`__NEXT_DATA__` extraction + record shaping.

The page hydrates a tRPC query cache into `__NEXT_DATA__`, so extraction is
a dictionary lookup by query key rather than DOM scraping -- markup changes
cannot break it, only a change in the data layer can.

Cache shape:

    props.pageProps.trpcState.json.queries[] = {
        queryKey: [["youtube", "user"], {input: {...}, type: "query"}],
        state: {data: {...}}
    }

Queries whose `state.data` is null (`auth.account.me`, `notice` for logged-out
visitors) are skipped rather than emitted as empty records.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL

_URL_PATH = re.compile(
    r"^(?:https?://)?(?:www\.)?socialblade\.com(/([a-z]+)/[^?#]+)", re.I
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_target(raw: str, default_platform: str) -> tuple[str, str]:
    """Accepts a full socialblade URL or a bare handle and returns
    (platform, path).

    A URL keeps its path **verbatim**: `/youtube/user/x`, `/youtube/c/x`
    and `/youtube/@x` address different channels upstream, so rewriting one
    into another silently returns the wrong creator (see constants.py).
    A bare handle is expanded to `/@<handle>` when it starts with "@", and
    to `/user/<handle>` otherwise.
    """
    s = (raw or "").strip()
    m = _URL_PATH.match(s)
    if m:
        return m.group(2).lower(), m.group(1).rstrip("/")
    handle = s.strip("/")
    if handle.startswith("@"):
        return default_platform, f"/{default_platform}/{handle}"
    return default_platform, f"/{default_platform}/user/{handle}"


def _queries(page_html: str) -> dict:
    """Return {queryName: data} for every cached query that actually has
    data, keyed by the dotted query name (e.g. "youtube.user")."""
    soup = BeautifulSoup(page_html, "lxml")
    node = soup.select_one("#__NEXT_DATA__")
    if not node:
        return {}
    try:
        payload = json.loads(node.string or node.get_text() or "")
    except (ValueError, TypeError):
        return {}
    queries = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("trpcState", {})
        .get("json", {})
        .get("queries", [])
    )
    out = {}
    for q in queries:
        data = (q.get("state") or {}).get("data")
        if data is None:
            continue
        key = q.get("queryKey") or []
        name = ".".join(key[0]) if key and isinstance(key[0], list) else str(key)
        out[name] = data
    return out


def parse_profile(page_html: str, platform: str, profile_url: str) -> dict:
    data = _queries(page_html)
    user = data.get(f"{platform}.user")
    if not isinstance(user, dict):
        return {}
    history = data.get(f"{platform}.history")
    record = dict(user)
    record["platform"] = platform
    record["profileUrl"] = profile_url
    if isinstance(history, list):
        record["history"] = history
        record["historyDays"] = len(history)
    return record


def parse_top(page_html: str, platform: str = "youtube") -> list[dict]:
    data = _queries(page_html)
    top = data.get(f"{platform}.top")
    if not isinstance(top, dict):
        return []
    creators = top.get("creators") or []
    out = []
    for rank, creator in enumerate(creators, start=1):
        if isinstance(creator, dict):
            row = dict(creator)
            row["platform"] = platform
            row["listRank"] = rank
            out.append(row)
    return out


def absolute(path: str) -> str:
    return path if path.startswith("http") else f"{BASE_URL}{path}"


def wrap(item: dict, input_value: str, source: str = "S1-ssr", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
