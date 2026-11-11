"""Query-field dispatch and record shaping.

OCR's search endpoint exposes three separate request fields
(`companyNameEnglish`, `companyNameNepali`, `companyRegistrationNumber`)
rather than one free-text box -- the CAMIS frontend itself is just a
name/registration-number toggle plus a Devanagari-aware textbox. This module
reproduces that same dispatch logic server-side so callers can pass one
plain string.
"""

import re

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
DIGITS_ONLY_RE = re.compile(r"^\d+$")


class NoResultsFound(Exception):
    pass


def build_request_body(query: str, search_by: str = "auto") -> dict:
    """Map one plain-string query to OCR's three-field request body."""
    body = {"companyNameEnglish": "", "companyNameNepali": "", "companyRegistrationNumber": ""}
    query = query.strip()

    if search_by == "registrationNumber":
        body["companyRegistrationNumber"] = query
        return body
    if search_by == "companyName":
        if DEVANAGARI_RE.search(query):
            body["companyNameNepali"] = query
        else:
            body["companyNameEnglish"] = query
        return body

    # auto-detect (default): digits-only -> registration number, Devanagari
    # script -> Nepali name field, anything else -> English name field.
    if DIGITS_ONLY_RE.match(query):
        body["companyRegistrationNumber"] = query
    elif DEVANAGARI_RE.search(query):
        body["companyNameNepali"] = query
    else:
        body["companyNameEnglish"] = query
    return body


def extract_records(payload: dict) -> list[dict]:
    """Parse the raw `{"status", "message", "data": [...]}` response.
    Raises NoResultsFound when `data` is a clean empty list (OCR's own
    "no match" signal -- confirmed on a deliberately-invented garbage
    query, `HTTP 200` with `"data": []`, not an error)."""
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response shape (not an object): {type(payload)!r}")
    rows = payload.get("data")
    if rows is None:
        raise RuntimeError(f"Unexpected response shape (no 'data' key): {list(payload.keys())!r}")
    if not rows:
        raise NoResultsFound
    return rows


def build_record(query: str, row: dict) -> dict:
    """Raw passthrough of OCR's own record shape -- only the envelope
    fields (_input/_source/_scrapedAt) are added, per this project's
    field-shape-verbatim convention."""
    from datetime import datetime, timezone

    record = dict(row)
    record["_input"] = query
    record["_source"] = "S1-camis-search-company-details"
    record["_scrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


def build_error(query: str, error: str, detail: str | None = None) -> dict:
    from datetime import datetime, timezone

    record = {
        "_input": query,
        "_scrapedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
