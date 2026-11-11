"""Response parsing + dataset-record builders.

Raw-passthrough per this project's convention -- upstream's own field names
(`company_name`, `company_number`, `registration_category`,
`registration_date`) are kept verbatim, not renamed.
"""

from datetime import datetime, timezone


class SearchApiError(Exception):
    """Raised when `searchDbApi` itself reports an error (e.g. no filter
    supplied server-side, malformed condition)."""


def parse_search_response(payload: dict) -> tuple[list[dict], int, bool]:
    if not isinstance(payload, dict):
        raise SearchApiError(f"Unexpected non-object response: {payload!r}")
    if payload.get("error"):
        raise SearchApiError(str(payload["error"]))
    rows = payload.get("data") or []
    total = payload.get("total", len(rows))
    truncated = bool(payload.get("truncated", False))
    return rows, total, truncated


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, row: dict, total: int, truncated: bool) -> dict:
    return {
        "_input": query,
        "_source": "S1-searchDbApi",
        "_scrapedAt": _now_iso(),
        "_totalAvailable": total,
        "_truncated": truncated,
        "company_name": row.get("company_name"),
        "company_number": row.get("company_number"),
        "registration_category": row.get("registration_category"),
        "registration_date": row.get("registration_date"),
    }


def build_error(query: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": _now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
