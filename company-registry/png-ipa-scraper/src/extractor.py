"""Parsing layer -- turns raw /Api/Corp/* JSON into dataset-ready records.

Kept separate from client.py (transport) per this portfolio's convention:
the client never inspects payload shape beyond HTTP status, and nothing here
makes an HTTP call.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream returned a shape we don't recognize -- investigate before the
    next run. Raised (not swallowed) so schema drift fails loud instead of
    silently truncating a run -- see .ai/conventions/error-handling.md."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_search_page(data: dict, term: str) -> tuple[list[dict], int]:
    """Validate + unpack one page of /Api/Corp/SearchCorp. Returns (records, totalRecordCount)."""
    if not isinstance(data, dict) or "records" not in data or "totalRecordCount" not in data:
        raise UnexpectedShape(
            f"SearchCorp response for term={term!r} missing records/totalRecordCount; "
            f"got keys={list(data.keys()) if isinstance(data, dict) else type(data)}"
        )
    records = data["records"]
    if not isinstance(records, list):
        raise UnexpectedShape(f"SearchCorp 'records' expected list, got {type(records)}")
    return records, data["totalRecordCount"]


def extract_search_record(rec: dict, term: str) -> dict:
    """One row from SearchCorp's 'records' array -- raw passthrough + envelope."""
    if "CorpId" not in rec or "Name" not in rec:
        raise UnexpectedShape(f"Search record for term={term!r} missing CorpId/Name; got keys={list(rec.keys())}")
    return {
        "_input": term,
        "_source": "S1-searchcorp",
        "_scrapedAt": utc_now_iso(),
        **rec,
    }


def is_not_found_profile(profile: dict) -> bool:
    """GetCorpProfile doesn't 404 on an invalid/nonexistent CorpId -- it
    returns HTTP 200 with a placeholder Corp object where CompanyName and
    RegistrationNumber are both the literal string "N/A". Confirmed live
    against a deliberately-invalid all-zero GUID."""
    corp = profile.get("Corp") or {}
    return corp.get("CompanyName") == "N/A" and corp.get("RegistrationNumber") == "N/A"


def extract_profile_record(profile: dict, input_val: str, source: str, extra: dict | None = None) -> dict:
    """Raw passthrough of GetCorpProfile's full response (Corp, Addresses,
    Activities, Officers, Directors, Secretaries, Shares, Owners,
    BeneficialOwners, Mortgages, ...). Note: Officers/Directors/Secretaries/
    Shares/Owners/BeneficialOwners are consistently EMPTY arrays for
    anonymous (unauthenticated) access -- that data is gated behind an IPA
    Online account login, which this actor never attempts (no-login
    policy). This is passed through as-is (empty arrays, not fabricated)
    rather than hidden -- see constants.py for the full recon note.
    """
    if not isinstance(profile, dict) or "Corp" not in profile:
        raise UnexpectedShape(
            f"GetCorpProfile response for input={input_val!r} missing 'Corp'; "
            f"got keys={list(profile.keys()) if isinstance(profile, dict) else type(profile)}"
        )
    if is_not_found_profile(profile):
        return extract_error(input_val, "not_found")

    record: dict = {}
    if extra:
        record.update(extra)
    record.update(profile)
    # Set last -- `extra` (a search_record) carries its own _input/_source/
    # _scrapedAt from extract_search_record(), which must not clobber this
    # function's own envelope for the merged/enriched record.
    record["_input"] = input_val
    record["_source"] = source
    record["_scrapedAt"] = utc_now_iso()
    return record


def extract_error(input_val: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_val,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
