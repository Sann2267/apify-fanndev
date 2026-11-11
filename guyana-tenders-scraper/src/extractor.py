"""Parsing/validation helpers for eprocure.gov.gy's two public JSON API
methods, plus the raw-passthrough record builders.

Both endpoints already return clean JSON (a Frappe `{"message": ...}`
envelope) -- there's no HTML to parse. The work here is: (1) unwrap the
Frappe envelope and surface its own error shape when present, (2) validate
the minimum expected field set so an upstream shape change fails loud
instead of silently shipping partial records, and (3) resolve relative
document paths to absolute, request-ready URLs.
"""

from datetime import datetime, timezone
from urllib.parse import quote, urljoin

from src.constants import BASE_URL

EXPECTED_LIST_FIELDS = {"project_id", "project_name", "agency", "current_state"}
EXPECTED_DETAIL_FIELDS = {"project_id", "project_name", "agency"}


class UnexpectedShape(Exception):
    """Upstream page/API shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class FrappeApiError(Exception):
    """The Frappe backend itself returned a structured error envelope
    (`{"exc_type": ..., "_server_messages": ...}`) instead of `{"message": ...}`
    -- e.g. an unknown/unpublished `project_id`. Carries the raw envelope so
    callers can surface it verbatim in `_errorDetail`."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unwrap_frappe_response(payload: dict):
    """Returns `payload["message"]`, or raises `FrappeApiError` if this is a
    Frappe error envelope (`exc`/`exc_type` present instead of `message`)."""
    if "message" in payload:
        return payload["message"]
    if "exc_type" in payload or "exc" in payload:
        raise FrappeApiError(repr(payload))
    raise UnexpectedShape(f"response has neither 'message' nor Frappe error keys: {sorted(payload.keys())}")


def _resolve_documents(docs) -> list[dict]:
    """Adds a `document_url` (absolute, percent-encoded) alongside each
    document's original `document_name`/`document_file` fields -- raw
    passthrough plus one derived convenience field, not a rename."""
    out = []
    for doc in docs or []:
        resolved = dict(doc)
        file_path = doc.get("document_file")
        if file_path:
            # Source paths can contain literal unencoded spaces (confirmed
            # live, e.g. "/files/SPN- P501759-CW-1.pdf") -- quote before
            # joining so the result is directly usable by an HTTP client.
            resolved["document_url"] = urljoin(BASE_URL, quote(file_path, safe="/"))
        else:
            resolved["document_url"] = None
        out.append(resolved)
    return out


def validate_list_row(row: dict) -> None:
    missing = EXPECTED_LIST_FIELDS - row.keys()
    if missing:
        raise UnexpectedShape(f"bid-opportunity row missing expected field(s) {missing}: has {sorted(row.keys())}")


def validate_detail(detail: dict) -> None:
    missing = EXPECTED_DETAIL_FIELDS - detail.keys()
    if missing:
        raise UnexpectedShape(f"project-advertisement detail missing expected field(s) {missing}: has {sorted(detail.keys())}")


def normalize_list_row(row: dict) -> dict:
    validate_list_row(row)
    out = dict(row)
    out["advertisement_documents"] = _resolve_documents(row.get("advertisement_documents"))
    return out


def normalize_detail(detail: dict) -> dict:
    validate_detail(detail)
    out = dict(detail)
    out["advertisement_documents"] = _resolve_documents(detail.get("advertisement_documents"))
    return out


# ---------------------------------------------------------------------------
# Record builders (raw passthrough + envelope)
# ---------------------------------------------------------------------------

def build_record(source: str, row: dict) -> dict:
    return {
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error(error: str, detail: str | None = None) -> dict:
    record = {
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
