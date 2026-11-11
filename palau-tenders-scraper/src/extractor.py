"""Parsing + record builders for palaugov.pw/rfp-bids/'s three procurement
category tables (BHR, CIP, Other Organizations) -- same 5-column shape,
normalized into one record type with a `category` field.
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import BASE


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def parse_tender_tables(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        raise UnexpectedShape(f"{label}: no <table> found on the page -- page layout may have changed")

    records = []
    for table in tables:
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        category = _clean(heading.get_text(" ", strip=True)) if heading else None

        rows = table.find_all("tr")
        if not rows:
            raise UnexpectedShape(f"{label}: a table has zero <tr> rows, not even a header -- page layout may have changed")

        for tr in rows[1:]:  # skip header row
            cells = tr.find_all(["td", "th"])
            if len(cells) < 5:
                continue  # stray/empty row (e.g. "Other Organizations" with nothing posted)
            texts = [_clean(c.get_text(" ", strip=True)) for c in cells]
            if not any(texts):
                continue  # a real but fully-empty placeholder row -- not a data row
            ref_cell = cells[2]
            link = ref_cell.find("a", href=True)
            records.append(
                {
                    "category": category,
                    "ministryOrDepartment": texts[0],
                    "description": texts[1],
                    "referenceNumber": texts[2],
                    "noticeUrl": urljoin(BASE, link["href"]) if link else None,
                    "openingDate": texts[3],
                    "closingDate": texts[4],
                }
            )
    return records


def build_tender_record(raw: dict) -> dict:
    return {
        "category": raw.get("category"),
        "ministryOrDepartment": raw.get("ministryOrDepartment"),
        "description": raw.get("description"),
        "referenceNumber": raw.get("referenceNumber"),
        "noticeUrl": raw.get("noticeUrl"),
        "openingDate": raw.get("openingDate"),
        "closingDate": raw.get("closingDate"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(fields: dict) -> dict:
    return {
        "_source": "S1-html-table-rfp-bids",
        "_scrapedAt": utc_now_iso(),
        "recordType": "CURRENT_TENDER",
        **fields,
    }


def build_error_record(error: str, detail: str | None = None) -> dict:
    record = {
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
