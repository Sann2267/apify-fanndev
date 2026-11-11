"""Raw-passthrough record builders for BCCAR's public business search.

BCCAR's `list/public/business.json` endpoint returns a columnar shape
(`Map` + `Records`) that `client.py` already zips into plain per-entity
dicts. This module just wraps each dict in the project's standard dataset
envelope (see `.ai/conventions/dataset-envelope.md`) without renaming or
restructuring any upstream field.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: dict, entity: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-public-business-search",
        "_scrapedAt": utc_now_iso(),
        **entity,
    }


def extract_error(query: dict, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
