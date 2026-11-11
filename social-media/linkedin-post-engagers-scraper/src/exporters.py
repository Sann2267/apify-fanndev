"""Export the run's records as JSON, NDJSON, CSV and XLSX key-value store files.

The Apify dataset is always the primary output; these files are an extra so a
buyer can download a ready-made spreadsheet without going through the dataset
export UI. Nested objects are flattened into dotted columns for the tabular
formats and left intact for JSON and NDJSON.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Callable

# Column order for the tabular exports; anything unlisted is appended
# alphabetically, so a new upstream field shows up rather than disappearing.
PREFERRED_COLUMNS: list[str] = []
SKIP_IN_TABLES: set[str] = set()
SHEET_TITLE = "Results"
FILE_STEM = "results"


def configure(
    preferred: list[str] | None = None,
    skip: set[str] | None = None,
    sheet: str | None = None,
    stem: str | None = None,
) -> None:
    """Point the shared exporter at one actor's column order and filenames."""
    global PREFERRED_COLUMNS, SKIP_IN_TABLES, SHEET_TITLE, FILE_STEM
    if preferred is not None:
        PREFERRED_COLUMNS = preferred
    if skip is not None:
        SKIP_IN_TABLES = skip
    if sheet is not None:
        SHEET_TITLE = sheet
    if stem is not None:
        FILE_STEM = stem


def flatten(record: dict, parent: str = "") -> dict:
    """Recursive dotted flattening; lists are JSON-encoded."""
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
    ordered = [column for column in PREFERRED_COLUMNS if column in seen]
    rest = sorted(column for column in seen if column not in set(ordered))
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
        writer.writerow({column: row.get(column, "") for column in columns})
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
    sheet.title = SHEET_TITLE[:31]
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


BUILDERS: dict[str, tuple[str, str, Callable[[list[dict]], bytes | None]]] = {
    "json": (".json", "application/json", to_json),
    "ndjson": (".ndjson", "application/x-ndjson", to_ndjson),
    "csv": (".csv", "text/csv", to_csv),
    "excel": (
        ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        to_xlsx,
    ),
}


async def write_exports(actor: Any, formats: list[str], records: list[dict]) -> None:
    """Write each requested export into the run's key-value store."""
    if not formats or not records:
        return
    store = await actor.open_key_value_store()
    for fmt in formats:
        spec = BUILDERS.get(fmt)
        if not spec:
            actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
            continue
        suffix, content_type, builder = spec
        payload = builder(records)
        if payload is None:
            actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
            continue
        filename = f"{FILE_STEM}{suffix}"
        await store.set_value(filename, payload, content_type=content_type)
        actor.log.info(f"Exported {filename} ({len(payload):,} bytes)")
