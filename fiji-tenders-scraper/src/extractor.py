"""Parsing + record builders for portal.tenderlink.com/financefiji's two
public tables: `current` (alltenders) and `awards` (tenderfunction) --
identical 3-column shape, `awards` additionally embeds "Awarded to: <company>"
at the end of the Summary cell for tenders that have been awarded.
"""

import re

from bs4 import BeautifulSoup

_AWARDED_TO_RE = re.compile(r"\s*Awarded to:\s*(.+)$", re.IGNORECASE)


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def _find_data_table(html: str, label: str):
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [_clean(c.get_text(" ", strip=True)) for c in rows[0].find_all(["td", "th"])]
        if header_cells and header_cells[0] == "Notice":
            return table
    raise UnexpectedShape(f"{label}: no table with a 'Notice' header column found -- page layout may have changed")


def parse_tender_rows(html: str, label: str) -> list[dict]:
    table = _find_data_table(html, label)
    rows = table.find_all("tr")

    records = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue  # stray/empty row
        reference = _clean(cells[0].get_text(" ", strip=True))
        summary_raw = _clean(cells[1].get_text(" ", strip=True))
        close_date = _clean(cells[2].get_text(" ", strip=True))
        if not reference and not summary_raw:
            continue

        awarded_to = None
        summary = summary_raw
        if summary_raw:
            m = _AWARDED_TO_RE.search(summary_raw)
            if m:
                awarded_to = _clean(m.group(1))
                summary = _clean(summary_raw[: m.start()])

        records.append(
            {
                "referenceNumber": reference,
                "summary": summary,
                "awardedTo": awarded_to,
                "dateTime": close_date,
            }
        )

    if not records:
        raise UnexpectedShape(f"{label}: header row parsed but zero data rows extracted -- page layout may have changed")
    return records


def build_tender_record(raw: dict) -> dict:
    return {
        "referenceNumber": raw.get("referenceNumber"),
        "summary": raw.get("summary"),
        "awardedTo": raw.get("awardedTo"),
        "dateTime": raw.get("dateTime"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


RECORD_TYPES = {"current": "CURRENT_TENDER", "awards": "TENDER_AWARD"}
SOURCE_TAGS = {
    "current": "S1-tenderlink-html-table-alltenders",
    "awards": "S1-tenderlink-html-table-awards",
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
