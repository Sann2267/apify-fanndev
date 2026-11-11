"""Parsing + record builders for procurement.gov.ki's `/tender-list`
chronological table.
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


def parse_tender_rows(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []  # legitimately the page past the last one -- caller decides how to treat this

    rows = table.find_all("tr")
    if not rows:
        raise UnexpectedShape(f"{label}: table has no <tr> rows at all -- page layout may have changed")

    header_cells = [_clean(c.get_text(" ", strip=True)) for c in rows[0].find_all(["td", "th"])]
    if not header_cells or "procuring entity" not in (header_cells[1] or "").lower():
        raise UnexpectedShape(f"{label}: header row doesn't match expected columns -- got {header_cells!r}")

    records = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue  # stray/empty row, not a data row
        link = cells[0].find("a", href=True)
        records.append(
            {
                "referenceNumber": _clean(cells[0].get_text(" ", strip=True)),
                "procuringEntity": _clean(cells[1].get_text(" ", strip=True)),
                "description": _clean(cells[2].get_text(" ", strip=True)),
                "openDate": _clean(cells[3].get_text(" ", strip=True)),
                "closeDate": _clean(cells[4].get_text(" ", strip=True)),
                "detailUrl": urljoin(BASE, link["href"]) if link else None,
            }
        )

    if not records:
        raise UnexpectedShape(f"{label}: header row parsed but zero data rows extracted -- page layout may have changed")
    return records


def build_tender_record(raw: dict) -> dict:
    return {
        "referenceNumber": raw.get("referenceNumber"),
        "procuringEntity": raw.get("procuringEntity"),
        "description": raw.get("description"),
        "openDate": raw.get("openDate"),
        "closeDate": raw.get("closeDate"),
        "detailUrl": raw.get("detailUrl"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(fields: dict) -> dict:
    return {
        "_source": "S1-html-table-tender-list",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER",
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
