"""Raw-passthrough record builders and query validation for CIPO's
`NameSearchPage/search` results.

CIPO's `NameSearchPage/search` returns a flat, well-shaped JSON object per
match -- no nested view-tree/node-graph to walk. Field names and values are
passed through verbatim, per this project's raw-passthrough convention.
"""

from datetime import datetime, timezone

from src.constants import _INVALID_QUERY_SUBSTRINGS


class InvalidQuery(Exception):
    """The query is blank/whitespace-only, or contains a character sequence
    (`'` or `--`) that upstream's `NameSearchPage/search` mishandles with an
    HTTP 500 `AccessViolationException`/`SqlException` ("DGS Error") instead
    of a normal result -- see constants.py. Rejected before sending rather
    than treating a genuine upstream bug as a transient/blocked failure."""


def validate_query(query: str) -> str:
    """Returns the stripped query, or raises `InvalidQuery`."""
    stripped = query.strip() if isinstance(query, str) else ""
    if not stripped:
        raise InvalidQuery("Query is blank or whitespace-only.")
    for bad in _INVALID_QUERY_SUBSTRINGS:
        if bad in stripped:
            raise InvalidQuery(
                f"Query {query!r} contains {bad!r}, which upstream's search endpoint "
                f"mishandles with an HTTP 500 error (see constants.py docstring) -- remove it and retry."
            )
    return stripped


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, row: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-namesearchpage",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def extract_error(query: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
