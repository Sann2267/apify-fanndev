"""Builds dataset-ready records from ANPI's own JSON row shape.

The API already returns clean, flat JSON per company -- no HTML/tree
parsing needed (contrast with `botswana-cipa-scraper` or
`malawi-cripc-scraper`). This module does raw passthrough of every field
ANPI returns (per .ai/CLAUDE.md principle #5), wrapped in this portfolio's
standard `_input`/`_source`/`_scrapedAt` envelope.
"""

from datetime import datetime, timezone

SOURCE = "S1-anpi-rest"


class UnexpectedShape(Exception):
    """Raised when the API response doesn't look like anything this client
    recognizes -- propagates and fails the run loudly rather than silently
    emitting an empty page, per .ai/CLAUDE.md principle #6."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query_label: str, row: dict) -> dict:
    return {
        "_input": query_label,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def extract_error(query_label: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query_label,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
