"""Raw-passthrough record builders for the Bahamas RGD's public search API.

Both `/public/entities` (current names) and `/public/entities/history`
(former/historical names) already return clean, flat-ish JSON per match --
no bespoke tree/delta format to normalize. This module just wraps each
upstream item in the project's standard dataset envelope
(see `.ai/conventions/dataset-envelope.md`) without renaming any upstream
field.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, item: dict, include_history: bool) -> dict:
    source = "S2-public-entities-history" if include_history else "S1-public-entities"
    return {
        "_input": query,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
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
