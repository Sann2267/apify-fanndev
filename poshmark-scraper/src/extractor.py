"""Parsing logic -- turns the `__INITIAL_STATE__` Vuex blob into
dataset-ready records.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming) -- Poshmark's own listing/seller objects are
already rich and self-describing (title, price, brand, condition,
size, creator_username, aggregates, ...), so records are the raw
upstream object plus the standard envelope tags.
"""

import json
from datetime import datetime, timezone

STATE_MARKER = "window.__INITIAL_STATE__="


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_balanced_json(text: str, start_idx: int) -> str | None:
    """Walk forward from `start_idx` (which must point at an opening
    `{`) counting brace depth, string-aware, until the matching close
    brace. See .ai/skills/balanced-brace-json.md -- this blob is 4-5MB
    of single-line minified JSON, too large/fragile for a regex."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1]
    return None


def extract_initial_state(html: str) -> dict:
    idx = html.find(STATE_MARKER)
    if idx < 0:
        raise UnexpectedShape("window.__INITIAL_STATE__ not found in page -- shape has likely changed.")
    idx += len(STATE_MARKER)
    blob = _extract_balanced_json(html, idx)
    if blob is None:
        raise UnexpectedShape("Could not find a balanced closing brace for __INITIAL_STATE__ -- shape has likely changed.")
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__INITIAL_STATE__ did not parse as JSON: {e}") from e


def wrap(item: dict, input_value: str, source: str = "S1-html") -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_browse_page(state: dict, browse_by: str, value: str) -> tuple[list[dict], dict]:
    """Returns (raw_items, more_dict) for one page. `more_dict` carries
    `next_max_id`/`is_next_max_id_present`/`total` for the caller's
    pagination loop -- see main.py's run_browse."""
    state_key = "$_brand" if browse_by == "brand" else "$_category"
    section = state.get(state_key)
    if section is None:
        raise UnexpectedShape(f"{state_key} missing from __INITIAL_STATE__ -- shape has likely changed.")

    grid = section.get("gridData")
    if grid is None:
        raise UnexpectedShape(f"{state_key}.gridData missing -- shape has likely changed.")

    items = grid.get("data")
    if items is None:
        raise UnexpectedShape(f"{state_key}.gridData.data missing -- shape has likely changed.")

    return items, (grid.get("more") or {})


def wrap_browse_items(items: list[dict], browse_by: str, value: str, grid_total: int | None) -> list[dict]:
    input_value = f"{browse_by}:{value}"
    return [wrap({**it, "_gridTotal": grid_total}, input_value) for it in items]


def extract_listing(state: dict, input_value: str) -> dict:
    details = state.get("$_listing_details")
    if details is None:
        raise UnexpectedShape("$_listing_details missing from __INITIAL_STATE__ -- shape has likely changed.")

    listing = details.get("listingDetails")
    if not listing:
        # A genuinely deleted/sold-and-removed listing still 200s on
        # some Poshmark URL shapes but carries an empty/near-empty
        # listingDetails -- treated as not-found rather than crashing.
        return None

    lister = details.get("listerData") or {}
    record = dict(listing)
    if lister:
        record["lister"] = lister
    return wrap(record, input_value)


def extract_seller(state: dict, username: str) -> dict:
    closet = state.get("$_closet")
    if closet is None:
        raise UnexpectedShape("$_closet missing from __INITIAL_STATE__ -- shape has likely changed.")

    user_info = closet.get("closetUserInfo") or {}
    data = user_info.get("data")
    if not data:
        return None

    return wrap(data, username)
