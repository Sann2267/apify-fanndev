"""Parsing for Panama DGCP's OCDS record-package responses, plus the
raw-passthrough record builders.

Both endpoints used by this actor (`/api/v1/records` list pages and
`/api/v1/record/{ocid}` single lookups) return the same wrapper shape: an
OCDS record *package* -- `version`/`publisher`/`license`/`publicationPolicy`/
`publishedDate` plus a `records` array, each entry carrying a `compiledRelease`
object (the merged, current-state view of that tender -- planning, tender,
awards, contracts, parties). This module unwraps that package and passes the
`compiledRelease` object through close to verbatim (raw-passthrough
convention), only adding the envelope fields the rest of this portfolio uses.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_records_page(data: dict) -> tuple[list[dict], str | None]:
    """Unwrap a `/api/v1/records` page into `(compiledReleases, nextCursorUrl)`.
    `nextCursorUrl` is `None` once the feed has no more pages. Raises
    `UnexpectedShape` if the top-level `records` key is missing entirely
    (e.g. an HTML/error page slipped through) -- an empty `records: []` list
    is NOT an error (a legitimate "no more results at this cursor" outcome)."""
    if not isinstance(data, dict) or "records" not in data:
        raise UnexpectedShape("'records' key missing from API response -- got: " + str(list(data.keys()) if isinstance(data, dict) else type(data)))

    compiled: list[dict] = []
    for i, rec in enumerate(data["records"]):
        cr = rec.get("compiledRelease") if isinstance(rec, dict) else None
        if cr is None:
            raise UnexpectedShape(f"records[{i}] missing 'compiledRelease'")
        compiled.append(cr)

    next_cursor = (data.get("links") or {}).get("next")
    return compiled, next_cursor


def parse_record_detail(data: dict, ocid: str) -> dict:
    """Unwrap a `/api/v1/record/{ocid}` response into its single
    `compiledRelease` object. Raises `UnexpectedShape` if the expected
    `records[0].compiledRelease` path isn't there (a 404 for a genuinely
    unknown ocid is handled separately by the caller -- this function is
    only called on a 200 response)."""
    records = data.get("records") if isinstance(data, dict) else None
    if not records:
        raise UnexpectedShape(f"no 'records' in detail response for ocid={ocid!r}")
    cr = records[0].get("compiledRelease") if isinstance(records[0], dict) else None
    if cr is None:
        raise UnexpectedShape(f"records[0] missing 'compiledRelease' for ocid={ocid!r}")
    return cr


def build_list_record(compiled_release: dict, filters: dict) -> dict:
    return {
        "_input": filters,
        "_source": "S1-ocds-records-api",
        "_scrapedAt": utc_now_iso(),
        **compiled_release,
    }


def build_detail_record(ocid: str, compiled_release: dict) -> dict:
    return {
        "_input": ocid,
        "_source": "S1-ocds-record-detail",
        "_scrapedAt": utc_now_iso(),
        **compiled_release,
    }


def build_error_record(input_value, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
