"""Parsing + record builders for procurement.gov.vc/eprocure's three public
listing pages: `current` and `closed` bids (identical 7-column table shape)
and `awards` (one row per year, one or more PDF links each).
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import EPROCURE


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def _cell_text(td) -> str | None:
    return _clean(td.get_text(" ", strip=True))


def _find_content_table(html: str, label: str):
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one("div.com-content-article__body")
    if body is None:
        raise UnexpectedShape(f"{label}: 'com-content-article__body' wrapper not found -- page layout may have changed")
    table = body.find("table")
    if table is None:
        raise UnexpectedShape(f"{label}: no <table> found inside the article body -- page layout may have changed")
    return table


# ---------------------------------------------------------------------------
# current / closed bids -- shared 7-column table shape
# ---------------------------------------------------------------------------

_BID_COLUMNS = (
    "no",
    "referenceNumber",
    "_description_cell",
    "procuringEntity",
    "procurementType",
    "tenderType",
    "submissionDeadline",
)


def parse_bid_rows(html: str, label: str) -> list[dict]:
    table = _find_content_table(html, label)
    rows = table.find_all("tr")
    if not rows:
        raise UnexpectedShape(f"{label}: table has no <tr> rows at all -- page layout may have changed")

    header_cells = [_cell_text(td) for td in rows[0].find_all(["td", "th"])]
    if not header_cells or "reference number" not in (header_cells[1] or "").lower():
        raise UnexpectedShape(f"{label}: header row doesn't match expected columns -- got {header_cells!r}")

    records = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 7:
            continue  # stray/empty row, not a data row
        record = dict(zip(_BID_COLUMNS, cells))
        desc_cell = record.pop("_description_cell")
        link = desc_cell.find("a")
        record = {k: _cell_text(v) for k, v in record.items()}
        record["title"] = _cell_text(link) if link else _cell_text(desc_cell)
        record["pdfUrl"] = urljoin(EPROCURE + "/", link["href"]) if link and link.get("href") else None
        records.append(record)

    if not records:
        raise UnexpectedShape(f"{label}: header row parsed but zero data rows extracted -- page layout may have changed")
    return records


def build_bid_record(list_type: str, raw: dict) -> dict:
    return {
        "no": raw.get("no"),
        "referenceNumber": raw.get("referenceNumber"),
        "title": raw.get("title"),
        "pdfUrl": raw.get("pdfUrl"),
        "procuringEntity": raw.get("procuringEntity"),
        "procurementType": raw.get("procurementType"),
        "tenderType": raw.get("tenderType"),
        "submissionDeadline": raw.get("submissionDeadline"),
    }


# ---------------------------------------------------------------------------
# awards -- one row per year, one or more {label, pdfUrl} document links
# ---------------------------------------------------------------------------


def parse_award_rows(html: str, label: str) -> list[dict]:
    table = _find_content_table(html, label)
    rows = table.find_all("tr")
    if not rows:
        raise UnexpectedShape(f"{label}: table has no <tr> rows at all -- page layout may have changed")

    header_cells = [_cell_text(td) for td in rows[0].find_all(["td", "th"])]
    if not header_cells or "year" not in (header_cells[0] or "").lower():
        raise UnexpectedShape(f"{label}: header row doesn't match expected columns -- got {header_cells!r}")

    records = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        year = _cell_text(cells[0])
        links = cells[1].find_all("a")
        if not links:
            continue
        for a in links:
            href = a.get("href")
            if not href:
                continue
            records.append(
                {
                    "year": year,
                    "documentLabel": _cell_text(a) or "Full Year",
                    "pdfUrl": urljoin(EPROCURE + "/", href),
                }
            )

    if not records:
        raise UnexpectedShape(f"{label}: header row parsed but zero document links extracted -- page layout may have changed")
    return records


def build_award_record(raw: dict) -> dict:
    return {
        "year": raw.get("year"),
        "documentLabel": raw.get("documentLabel"),
        "pdfUrl": raw.get("pdfUrl"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


RECORD_TYPES = {"current": "CURRENT_BID", "closed": "CLOSED_BID", "awards": "AWARD_DOCUMENT"}
SOURCE_TAGS = {
    "current": "S1-html-table-current-bids",
    "closed": "S1-html-table-closed-bids",
    "awards": "S1-html-table-contract-award-notices",
}


def build_record(list_type: str, fields: dict) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": SOURCE_TAGS.get(list_type, list_type),
        "_scrapedAt": utc_now_iso(),
        "recordType": RECORD_TYPES.get(list_type, list_type),
        **fields,
    }


def build_error_record(list_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": f"list:{list_type}",
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
