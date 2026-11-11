"""Response parsing and raw-passthrough record builders for CIPO's
`loadInfoProc` API (see `constants.py` for the full recon summary).

Every response is a JSON object shaped either `{"rows": [...]}` (success,
`rows` possibly empty) or `{"message": "..."}` (upstream error -- no `rows`
key at all). There is no HTTP-status signal for either case -- both come
back as `200 OK`.
"""

import re
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way that can't be interpreted
    (neither a `rows` list nor a `message` string). Investigate before the
    next run -- do not silently emit a partial/empty record."""


class UpstreamError(Exception):
    """CIPO's own API returned `{"message": "..."}` instead of rows -- most
    often its own "Divide by zero error encountered" bug on an overly broad
    or malformed query (see constants.py). Not a block/WAF signal."""


class InvalidQuery(Exception):
    """The query contains a character (',' or '=') that upstream's naive
    `"key=0,query=<term>"` string parsing mishandles -- a comma silently
    truncates the search instead of erroring, and '=' triggers the same
    "Divide by zero" bug as an overly broad query. Rejected client-side
    before sending rather than risk a silently-wrong match set."""


class NoResultsFound(Exception):
    """The search legitimately matched zero entities -- `rows: []` with no
    `message` key, i.e. a clean, well-formed empty result."""


_INVALID_QUERY_CHARS = (",", "=")


def validate_query(query: str) -> None:
    for ch in _INVALID_QUERY_CHARS:
        if ch in query:
            raise InvalidQuery(
                f"Query {query!r} contains {ch!r}, which upstream's search "
                f"endpoint mishandles (see constants.py docstring) -- remove it and retry."
            )


def parse_response(data: dict) -> list[dict]:
    """Returns the `rows` list, or raises `UpstreamError`/`UnexpectedShape`."""
    if not isinstance(data, dict):
        raise UnexpectedShape(f"response body was not a JSON object: {data!r}")
    if "message" in data and "rows" not in data:
        raise UpstreamError(data["message"])
    if "rows" not in data:
        raise UnexpectedShape(f"response had neither 'rows' nor 'message': {sorted(data)}")
    return data["rows"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, search_type: str, row: dict, detail: dict | None = None) -> dict:
    record = {
        "_input": query,
        "_searchType": search_type,
        "_source": "S1-ocrs-entitysearch+entityinfo" if detail else "S1-ocrs-entitysearch",
        "_scrapedAt": utc_now_iso(),
        **row,
    }
    if detail:
        record.update(detail)
    return record


def extract_error(query: str, search_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_searchType": search_type,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
