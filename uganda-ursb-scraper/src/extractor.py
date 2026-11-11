"""Raw-passthrough record builders for URSB's name-search API.

URSB's `name-search` endpoint already returns clean, well-shaped JSON per
entity -- unlike CIPA/PACRA there is no bespoke node-tree or delta-wire
format to flatten. This module just wraps each upstream entity dict in the
project's standard dataset envelope (see `.ai/conventions/dataset-envelope.md`)
without renaming or restructuring any upstream field.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, entity: dict, truncated: bool = False) -> dict:
    record = {
        "_input": query,
        "_source": "S1-nir-name-search",
        "_scrapedAt": utc_now_iso(),
        **entity,
    }
    if truncated:
        record["_warning"] = "pagination_truncated_by_timeout"
    return record


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
