"""Parsing logic -- turns one of PPDA's procurement-notice board pages into
records.

See client.py / constants.py for how each page is obtained. All five
notice-board pages (tenders, award-notices, intentions-to-award,
debarments, admin-review-notices) share the same Bootstrap+DataTables
template: a `<table id="...">` with a `<thead>` of `<th>` column labels and
a `<tbody>` of one `<tr>` per notice, plus a per-row "Attachment"/
"Downloads" column that is a download button, not text. This module reads
the header row to decide field names dynamically rather than hardcoding a
fixed column set per notice type, so it works unmodified across all five
(and would still work if PPDA added/reordered a column upstream).
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import ATTACHMENT_HEADERS, EMPTY_STATE_MARKER, HEADER_FIELD_MAP, NOTICE_TYPES

SOURCE = "S1-ppda-notice-tables"

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_header(raw: str) -> str:
    return raw.strip().lower().rstrip(".")


def _slugify(raw: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", raw)
    if not words:
        return "field"
    head, *rest = words
    return head.lower() + "".join(w.capitalize() for w in rest)


def _first_link(cells) -> str | None:
    for cell in cells:
        for a in cell.find_all("a"):
            href = a.get("href")
            if href and href.strip():
                return href.strip()
    return None


def parse_notice_table(html_text: str, notice_type: str) -> list[dict]:
    """Returns a list of raw row dicts (field name -> text value), plus an
    "_attachmentUrl" key when a download link is present on that row.
    Raises UnexpectedShape if the page structure doesn't match what this
    actor was built against. An empty list is a valid, non-error result
    (either PPDA's own "No publications available" empty state, or a table
    present with zero data rows).
    """
    meta = NOTICE_TYPES[notice_type]
    table_id = meta["table_id"]

    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", id=table_id)

    if table is None:
        if EMPTY_STATE_MARKER in html_text.lower():
            return []
        raise UnexpectedShape(
            f"No table with id='{table_id}' found on the {meta['label']} page, and no "
            f"'{EMPTY_STATE_MARKER}' empty-state marker either -- page shape has likely changed."
        )

    thead = table.find("thead")
    if thead is None:
        raise UnexpectedShape(f"Table '{table_id}' has no <thead> -- page shape has likely changed.")
    raw_headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]
    if not raw_headers:
        raise UnexpectedShape(f"Table '{table_id}' has an empty <thead> -- page shape has likely changed.")
    normalized = [_normalize_header(h) for h in raw_headers]
    if "title" not in normalized:
        raise UnexpectedShape(f"Table '{table_id}' headers don't include 'Title': {raw_headers!r} -- page shape has likely changed.")

    tbody = table.find("tbody")
    if tbody is None:
        raise UnexpectedShape(f"Table '{table_id}' has no <tbody> -- page shape has likely changed.")

    field_names = []
    for h in normalized:
        if h in ATTACHMENT_HEADERS:
            field_names.append(None)  # handled separately via _first_link
        else:
            field_names.append(HEADER_FIELD_MAP.get(h, _slugify(h)))

    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != len(field_names):
            continue  # skip malformed/stray rows rather than crash the whole run
        row: dict = {}
        for field_name, cell in zip(field_names, cells):
            if field_name is None:
                continue
            row[field_name] = cell.get_text(" ", strip=True)
        attachment_url = _first_link(cells)
        if attachment_url:
            row["_attachmentUrl"] = attachment_url
        rows.append(row)

    return rows


def build_record(row_index: int, row: dict, notice_type: str, run_label: str) -> dict:
    record = {
        "_input": run_label,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "_rowIndex": row_index,
        "noticeType": notice_type,
    }
    for key, value in row.items():
        if key == "_attachmentUrl":
            continue
        if value:
            record[key] = value
    if row.get("_attachmentUrl"):
        record["attachmentUrl"] = row["_attachmentUrl"]
    closing_date = row.get("closingDate")
    if closing_date and ISO_DATE_RE.match(closing_date):
        record["isClosed"] = closing_date < datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return record


def build_error_record(notice_type: str, run_label: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": run_label,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "noticeType": notice_type,
        "_error": error_kind,
        "_errorDetail": detail,
    }
