"""Raw-passthrough record builders for ABIPCO search results.

ABIPCO's `NameSearchPage/search` already returns a flat, well-shaped JSON
object per match -- no nested view-tree/node-graph to walk (unlike the
Verne/Foster Moore platforms used by some sibling registries in this
portfolio). Field names and values are passed through verbatim, per this
project's raw-passthrough convention.
"""

from datetime import datetime, timezone


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
