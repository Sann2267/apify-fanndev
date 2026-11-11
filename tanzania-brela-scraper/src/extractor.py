"""Response parsing and raw-passthrough record builders for BRELA ORS's
public search JSON API.

The API returns `{"Map": [<field names>], "Records": [[<values>], ...],
"Result": "OK", "TotalRecordCount": N}` -- a columnar "map + rows" shape
rather than a list of objects, presumably to save bandwidth. `zip_record`
turns each row back into a `{field_name: value}` dict using the response's
OWN `Map` (not a hardcoded field list), so a field BRELA adds/removes/
reorders upstream is reflected automatically instead of silently
misaligning columns.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def parse_search_response(data: dict) -> tuple[list[dict], int]:
    """Returns `(rows, total_record_count)` from a parsed JSON response body.
    Raises `UnexpectedShape` if the response doesn't look like the search
    list shape at all (e.g. an HTML error page slipped through as 200, or
    BRELA changed the envelope)."""
    if not isinstance(data, dict) or "Records" not in data or "Map" not in data:
        raise UnexpectedShape(f"response missing Map/Records keys; got keys={sorted(data) if isinstance(data, dict) else type(data)}")
    field_names = data["Map"]
    rows = [dict(zip(field_names, record, strict=True)) for record in data["Records"]]
    total = data.get("TotalRecordCount", len(rows))
    return rows, total


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, row: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-ors-searchresult",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error(query: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
