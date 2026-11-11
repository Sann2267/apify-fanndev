"""Export the run's records as JSON, NDJSON, CSV and XLSX key-value store files.

The Apify dataset is always the primary output; these files are an extra so a
buyer can download a ready-made spreadsheet without going through the dataset
export UI. Nested objects (reviewer, ownerResponse, sentiment) are flattened
into dotted columns for the tabular formats and left intact for JSON/NDJSON.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

# Column order for the tabular exports. Anything not listed is appended
# alphabetically, so a new upstream field shows up rather than disappearing.
# Column order tuned for outreach: the fields a salesperson actually works
# from come first, so the CSV is usable without rearranging columns.
PREFERRED_COLUMNS = [
    "name",
    "primaryCategory",
    "phone",
    "phoneE164",
    "emails",
    "website",
    "websiteDomain",
    "address",
    "region",
    "latitude",
    "longitude",
    "rating",
    "reviewsCount",
    "openNow",
    "socialProfiles.instagram",
    "socialProfiles.facebook",
    "socialProfiles.linkedin",
    "socialProfiles.whatsapp",
    "socialProfiles.tiktok",
    "socialProfiles.youtube",
    "socialProfiles.twitter",
    "googleMapsUrl",
    "placeId",
    "featureId",
    "enrichmentStatus",
    "_searchQuery",
    "recordType",
]

SKIP_IN_TABLES = {"openingHours", "addressParts", "attributes"}


def flatten(record: dict, parent: str = "") -> dict:
    """One level of dotted flattening; lists are JSON-encoded."""
    flat: dict[str, Any] = {}
    for key, value in record.items():
        name = f"{parent}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        elif isinstance(value, list):
            flat[name] = json.dumps(value, ensure_ascii=False) if value else ""
        else:
            flat[name] = value
    return flat


def _columns(rows: list[dict]) -> list[str]:
    seen: set[str] = set()
    for row in rows:
        seen.update(row)
    ordered = [c for c in PREFERRED_COLUMNS if c in seen]
    rest = sorted(c for c in seen if c not in set(ordered))
    return ordered + rest


def _tabular_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        trimmed = {k: v for k, v in record.items() if k not in SKIP_IN_TABLES}
        rows.append(flatten(trimmed))
    return rows


def to_json(records: list[dict]) -> bytes:
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


def to_ndjson(records: list[dict]) -> bytes:
    lines = (json.dumps(record, ensure_ascii=False) for record in records)
    return ("\n".join(lines) + "\n").encode("utf-8")


def to_csv(records: list[dict]) -> bytes:
    rows = _tabular_rows(records)
    if not rows:
        return b""
    columns = _columns(rows)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    # BOM so Excel opens UTF-8 CSV correctly on Windows.
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def to_xlsx(records: list[dict]) -> bytes | None:
    """Build an XLSX workbook. Returns None if openpyxl is unavailable."""
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except ImportError:
        return None

    rows = _tabular_rows(records)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Reviews"
    if not rows:
        sheet.append(["no records"])
    else:
        columns = _columns(rows)
        sheet.append(columns)
        for row in rows:
            sheet.append([_xlsx_safe(row.get(column, "")) for column in columns])
        sheet.freeze_panes = "A2"
        for index, column in enumerate(columns, start=1):
            width = max(len(column) + 2, 12)
            sheet.column_dimensions[get_column_letter(index)].width = min(width, 60)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _xlsx_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        # Excel rejects control characters and caps cells at 32767 chars.
        if isinstance(value, str):
            cleaned = "".join(ch for ch in value if ch >= " " or ch in "\t\n")
            return cleaned[:32767]
        return value
    return json.dumps(value, ensure_ascii=False)[:32767]


BUILDERS = {
    "json": ("reviews.json", "application/json", to_json),
    "ndjson": ("reviews.ndjson", "application/x-ndjson", to_ndjson),
    "csv": ("reviews.csv", "text/csv", to_csv),
    "excel": ("reviews.xlsx",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
              to_xlsx),
}
