"""Response parsing and raw-passthrough record builders for ROCIP's public
search JSON API.

The API returns `{"rows": [{...}, ...]}` -- a plain list of objects (unlike
Tanzania BRELA's columnar "Map + Records" shape), so no zip/realignment is
needed. Each object is passed straight through as the output record, per
this project's raw-passthrough convention.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def parse_search_response(data: dict) -> list[dict]:
    """Returns the list of entity-row dicts from a parsed JSON response
    body. Raises `UnexpectedShape` if the response doesn't look like the
    search result shape at all (e.g. an HTML error page slipped through as
    200, or ROCIP changed the envelope)."""
    if not isinstance(data, dict) or "rows" not in data:
        raise UnexpectedShape(f"response missing 'rows' key; got keys={sorted(data) if isinstance(data, dict) else type(data)}")
    rows = data["rows"]
    if not isinstance(rows, list):
        raise UnexpectedShape(f"'rows' is not a list; got {type(rows)}")
    return rows


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, mode: str, row: dict) -> dict:
    return {
        "_input": query,
        "_searchMode": mode,
        "_source": "S1-ocrs-entitysearch",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error(query: str, mode: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_searchMode": mode,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
