"""Locating and reading the embed page's server-rendered state blob.

Every embed route renders one `<script id="__FRONTITY_CONNECT_STATE__">` element.
Its shape is::

    {
      "source": {"data": {"<the route path>": { ...the payload... }}},
      "router": {...}, "abtest": {...}, "frontity": {...}
    }

The payload is keyed by the route path itself (`"/embed/@complex"`,
`"/embed/music/7301919715965077506"`), so it is read positionally rather than by
name -- TikTok changes the path for every target, and has already shipped two
different payload shapes under it:

* a **video** payload: `{"videoData": {...}, "pageName": "video_v2"}`
* a **playlist** payload: `{"videoList": [...], "embedInfo": {...},
  "playlistType": "hashtag"|"music", "pageName": "tag"|"music"}`
* a **user** payload: `{"userInfo": {...}}`

`ShapeError` is raised loudly rather than returning an empty result: a missing
state element means TikTok moved the payload and the parser needs updating, which
is a different problem from a target that genuinely has no data.
"""

from __future__ import annotations

import json
import re

from src.constants import STATE_SCRIPT_ID

_STATE_RE = re.compile(
    r'<script id="' + re.escape(STATE_SCRIPT_ID) + r'"[^>]*>(.*?)</script>',
    re.S,
)


class ShapeError(Exception):
    """The embed page did not carry the state blob this parser expects."""


def parse_state(html: str) -> dict:
    """Return the decoded `__FRONTITY_CONNECT_STATE__` object."""
    match = _STATE_RE.search(html or "")
    if not match:
        raise ShapeError(
            f"no <script id={STATE_SCRIPT_ID}> in a {len(html or '')}-byte response"
        )
    try:
        state = json.loads(match.group(1))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ShapeError(f"state blob is not valid JSON: {exc}") from exc
    if not isinstance(state, dict):
        raise ShapeError(f"state blob decoded to {type(state).__name__}, expected object")
    return state


def route_payload(state: dict) -> dict:
    """Pull the single route-keyed payload out of `source.data`.

    Read positionally: the key is the request path, which differs per target.
    Routes other than the requested one (`"strategy"`, which TikTok adds
    alongside) are skipped by requiring a payload that names a page.
    """
    data = (state.get("source") or {}).get("data")
    if not isinstance(data, dict) or not data:
        raise ShapeError("state blob has no source.data object")
    candidates = [
        value for key, value in data.items()
        if isinstance(value, dict) and (
            "pageName" in value or "videoData" in value or "userInfo" in value
        )
    ]
    if not candidates:
        raise ShapeError(
            "source.data carried no route payload; keys were "
            + ", ".join(sorted(data)[:6])
        )
    return candidates[0]


def assert_found(payload: dict, what: str) -> None:
    """Raise when the embed rendered its error route instead of an entity.

    TikTok reports a missing entity inside a `HTTP 200` page, so this is the only
    place a not-found can be detected for an existing route.
    """
    if payload.get("isError") is True:
        raise LookupError(
            f"{what} does not exist (embed rendered its error route with HTTP 200)"
        )
    code = payload.get("customErrorCode") or 0
    status = payload.get("code")
    if code:
        raise LookupError(f"{what} returned customErrorCode={code}")
    if status is not None and status != 200:
        raise LookupError(f"{what} returned code={status} inside the embed state")


def first_int(value, default=None):
    """TikTok mixes ints and numeric strings in the same field (`heartCount`)."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = value.strip()
        if digits.isdigit():
            return int(digits)
    return default


def first_url(value):
    """Cover/avatar fields arrive as a list of equivalent CDN urls."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
    return None
