"""Parsing helpers for ProcureTT's GravityView listing/detail tables, plus
the raw-passthrough record builders.

Rows are parsed by each `<td>`'s `data-label` attribute (present on every
cell for GravityView's own responsive CSS) rather than a fixed column
index -- resilient to a future column reorder. The label set is still
checked against a per-notice-type minimum on every page, so a real upstream
layout change raises `UnexpectedShape` instead of silently mis-mapping or
dropping columns.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ENTRY_ID_RE = re.compile(r"/entry/(\d+)")
DISPLAYING_RE = re.compile(r"Displaying\s+([\d,]+)\s*-\s*([\d,]+)\s*of\s*([\d,]+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def extract_pagination(html: str) -> tuple[int | None, int | None]:
    """Returns `(total, page_size)` parsed from the "Displaying `X - Y` of
    `Z`" banner. Returns `(None, None)` when the banner is absent -- some
    views (e.g. pre-qualification notices) render no pagination widget at
    all when every row fits on one page; callers should treat the rows
    already fetched as the complete set in that case."""
    m = DISPLAYING_RE.search(html)
    if not m:
        return None, None
    start, end, total = (_int(g) for g in m.groups())
    return total, (end - start + 1)


def _cell_value(td):
    """A single table cell's value -- handles the three shapes ProcureTT
    renders: a bulleted `Lines of Business` list, a nested Gravity Forms
    "list field" table (Level 4 code/name pairs, detail pages only), a
    document-download link, or plain text."""
    ul = td.find("ul", class_="bulleted")
    if ul is not None:
        return [li.get_text(strip=True) for li in ul.find_all("li")]

    nested_table = td.find("table", class_="gfield_list")
    if nested_table is not None:
        thead = nested_table.find("thead")
        headers = [th.get_text(strip=True) for th in thead.find_all("th")] if thead else []
        out = []
        tbody = nested_table.find("tbody")
        for tr in tbody.find_all("tr") if tbody else []:
            cells = tr.find_all("td")
            if not cells:
                continue
            out.append({(headers[i] if i < len(headers) else f"col{i}"): c.get_text(strip=True) for i, c in enumerate(cells)})
        return out

    a = td.find("a", href=True)
    if a is not None and ("gf-download" in a["href"] or "gk-download" in a["href"]):
        return {"text": a.get_text(strip=True) or None, "url": a["href"]}

    return td.get_text(strip=True) or None


def _row_entry_id(tr) -> str | None:
    """Searches the whole row for a GravityView entry-detail link
    (`.../wp-json/gravityview/v1/view/<viewId>/entry/<id>` or the
    pretty-permalink `.../entry/<id>/`) -- observed on different columns
    across notice types (the linked column is the tender reference number
    for tenders, but the public-body name for pre-qualification notices), so
    this searches every `<a href>` in the row rather than assuming a fixed
    column."""
    for a in tr.find_all("a", href=True):
        m = ENTRY_ID_RE.search(a["href"])
        if m:
            return m.group(1)
    return None


def parse_listing_page(html: str, expected_labels: set[str]) -> list[dict]:
    """Returns raw rows from a ProcureTT listing table, one dict per notice,
    keyed by the source's own column labels verbatim (e.g. "Public Body",
    "Tender Reference No."). Each row also carries `_entryId` (the
    GravityView entry id backing this row, or `None` if this notice type has
    no per-entry detail page). Raises `UnexpectedShape` if a row is missing
    any label in `expected_labels`."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="gv-table-view")
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        return []

    out = []
    for tr in tbody.find_all("tr", recursive=False):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        row = {}
        for td in cells:
            label = td.get("data-label")
            if not label:
                raise UnexpectedShape(f"listing row cell has no data-label attribute: {td}")
            row[label] = _cell_value(td)
        missing = expected_labels - row.keys()
        if missing:
            raise UnexpectedShape(f"listing row missing expected column(s) {missing}: has {sorted(row.keys())}")
        row["_entryId"] = _row_entry_id(tr)
        out.append(row)
    return out


def parse_detail_page(html: str) -> dict:
    """Returns the field set from a ProcureTT per-entry detail page
    (`{path}entry/<id>/`), keyed by the source's own field labels verbatim
    -- typically a superset of the listing row's columns (e.g. tenders add
    "Notice Type", "Date of Issuance", "Lines of Business (Level 4)",
    "Submission Deadline Time"). Raises `UnexpectedShape` if the detail
    table itself is missing (a real layout change, not "notice type has no
    detail page" -- callers only invoke this for notice types confirmed to
    have one)."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="gv-table-view-content")
    if table is None:
        raise UnexpectedShape("detail page: table.gv-table-view-content not found")
    tbody = table.find("tbody")
    if tbody is None:
        raise UnexpectedShape("detail page: table.gv-table-view-content has no <tbody>")

    out = {}
    for tr in tbody.find_all("tr", recursive=False):
        th = tr.find("th")
        td = tr.find("td")
        if th is None or td is None:
            continue
        out[th.get_text(strip=True)] = _cell_value(td)
    return out


# ---------------------------------------------------------------------------
# Record builders (raw passthrough + envelope)
# ---------------------------------------------------------------------------

def build_record(notice_type: str, source: str, row: dict) -> dict:
    return {
        "_noticeType": notice_type,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error(notice_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_noticeType": notice_type,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
