"""Record shaping -- raw passthrough of Luma's own JSON shape plus the
portfolio-standard envelope tags.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming) and nested structures (an event's `calendar`,
`hosts`, `geo_address_info`, `ticket_info`; a calendar's
`featured_items`) are kept intact rather than exploded into separate
rows.
"""

import re
from datetime import datetime, timezone

_SLUG_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:lu\.ma|luma\.com)/", re.IGNORECASE)


def extract_slug(raw: str) -> str:
    """Accepts a bare slug ("sggq2oi9"), a path ("lu.ma/sggq2oi9"), or a
    full URL ("https://lu.ma/sggq2oi9?query=..") and returns just the
    slug Luma's own `/url` resolver expects."""
    s = raw.strip()
    s = _SLUG_RE.sub("", s)
    s = s.split("?")[0].split("#")[0]
    return s.strip("/")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str = "S1-api", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
