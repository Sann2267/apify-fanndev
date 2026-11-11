"""Parsing logic -- turns NPPA's "Bids / Tenders" TablePress page into records.

See client.py / constants.py for how the page is obtained. The page has
exactly one relevant table (`#tablepress-1`) with 5 columns: Bidding
Organization | Date Posted | Expiration Date | Description of Bidding |
Download Bid (a link to a PDF). One `<tr>` per tender notice.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SOURCE = "S1-bid-tenders-table"

EXPECTED_HEADERS = [
    "Bidding Organization",
    "Date Posted",
    "Expiration Date",
    "Description of Bidding",
    "Download Bid",
]


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_loose_date(raw: str) -> str | None:
    """Best-effort parse of NPPA's inconsistently formatted DD-MM-YYYY dates
    (e.g. "14-08-2026", "30- 04-2026", "13-4-2026", "23-04-26"). Returns an
    ISO "YYYY-MM-DD" string, or None if the value genuinely can't be parsed
    -- never raises, since this is known-dirty upstream data, not a schema
    change worth failing loudly over.
    """
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw.strip())
    parts = cleaned.split("-")
    if len(parts) != 3:
        return None
    day_s, month_s, year_s = parts
    if len(year_s) == 2:
        year_s = "20" + year_s
    try:
        day, month, year = int(day_s), int(month_s), int(year_s)
        return datetime(year, month, day, tzinfo=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def parse_bid_page(html_text: str) -> list[dict]:
    """Returns a list of raw row dicts:
    {"biddingOrganization", "datePosted", "expirationDate",
     "descriptionOfBidding", "documentUrl"}
    Raises UnexpectedShape if the table/columns don't match what this actor
    was built against.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", id="tablepress-1") or soup.find("table", class_=re.compile("tablepress"))
    if table is None:
        raise UnexpectedShape("No table with id='tablepress-1' (or *.tablepress class) found on /bid/ -- page shape has likely changed.")

    header_cells = table.find("thead")
    if header_cells is not None:
        headers = [th.get_text(" ", strip=True) for th in header_cells.find_all("th")]
        if headers[:5] != EXPECTED_HEADERS:
            raise UnexpectedShape(f"Table headers changed: expected {EXPECTED_HEADERS}, got {headers}")

    body = table.find("tbody")
    if body is None:
        raise UnexpectedShape("Table has no <tbody> -- page shape has likely changed.")

    rows = []
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue  # skip malformed/stray rows rather than crash the whole run
        doc_url = None
        for a in cells[4].find_all("a"):
            href = a.get("href")
            if href:
                doc_url = href.strip()
                break
        rows.append(
            {
                "biddingOrganization": cells[0].get_text(" ", strip=True),
                "datePosted": cells[1].get_text(" ", strip=True),
                "expirationDate": cells[2].get_text(" ", strip=True),
                "descriptionOfBidding": cells[3].get_text(" ", strip=True),
                "documentUrl": doc_url,
            }
        )

    if not rows:
        raise UnexpectedShape("Table found but zero data rows parsed -- page shape has likely changed.")

    return rows


def build_record(row_index: int, row: dict, run_label: str) -> dict:
    date_posted_iso = _parse_loose_date(row["datePosted"])
    expiration_iso = _parse_loose_date(row["expirationDate"])
    is_expired = None
    if expiration_iso is not None:
        is_expired = expiration_iso < datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record = {
        "_input": run_label,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "_rowIndex": row_index,
        "biddingOrganization": row["biddingOrganization"],
        "datePosted": row["datePosted"],
        "expirationDate": row["expirationDate"],
        "descriptionOfBidding": row["descriptionOfBidding"],
    }
    # Optional/nullable fields are omitted entirely rather than sent as an
    # explicit JSON `null` -- the dataset schema declares these as plain
    # `string`/`boolean`, and Apify's schema validation rejects a `null`
    # against a non-nullable type. "Absent" is how this actor represents
    # "couldn't be determined", matching the sibling registry actors'
    # convention (e.g. `matchedBusinessName` present only when relevant).
    if date_posted_iso is not None:
        record["datePostedIso"] = date_posted_iso
    if expiration_iso is not None:
        record["expirationDateIso"] = expiration_iso
    if is_expired is not None:
        record["isExpired"] = is_expired
    if row["documentUrl"]:
        record["documentUrl"] = row["documentUrl"]
    return record


def build_error_record(run_label: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": run_label,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
