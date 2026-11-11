"""Parsing helpers for GOJEP's server-rendered listing tables (`table#T01`)
plus the raw-passthrough record builders.

Both tables used by this actor ("opened bid details" and "contract award
notices") are plain HTML `<table>`s with a fixed column count per notice
type -- no JSON blob, no client-side rendering. A fixed-index column map is
used (not header-text matching) because header cells carry sort-link markup
rather than clean text; the column count is still checked against the
expected value on every page so a real upstream layout change raises
`UnexpectedShape` instead of silently mis-mapping columns.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESOURCE_ID_RE = re.compile(r"resourceId=(\d+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """Legitimately zero rows for this notice type/page (e.g. requested a
    page past the last one) -- distinct from an upstream shape change."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(cell) -> str:
    return cell.get_text(strip=True) if cell else ""


def _link_href(cell) -> str | None:
    a = cell.find("a") if cell else None
    return a["href"] if a and a.has_attr("href") else None


def _resource_id(href: str | None) -> str | None:
    if not href:
        return None
    m = RESOURCE_ID_RE.search(href)
    return m.group(1) if m else None


def extract_total_count(html: str) -> int | None:
    """Parses `| Displaying: <strong>1-10</strong> | <strong>81,157</strong>
    results in total.` -- returns None if the page has zero rows (the
    "Displaying" banner itself is absent in that case, not just the number)."""
    m = re.search(r"<strong>([\d,]+)</strong>\s*results in total", html)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def extract_pager_prefix(html: str) -> str | None:
    """Finds the `d-<digits>` table-instance id embedded in this page's own
    sort/page links (e.g. `?d-3680175-p=2` or `?d-16531-s=procedure`).
    Returns None if no such link is present (e.g. a zero-row page has no
    sortable header links) -- callers should fall back to treating the
    current page as the only page in that case."""
    m = re.search(r"[?&](d-\d+)-(?:p|s|o|n)=", html)
    return m.group(1) if m else None


def _find_table_rows(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="T01")
    if table is None:
        raise UnexpectedShape("table#T01 not found on listing page")
    tbody = table.find("tbody")
    if tbody is None:
        raise UnexpectedShape("table#T01 has no <tbody>")
    return tbody.find_all("tr", recursive=False)


# ---------------------------------------------------------------------------
# "Opened bid details" listing (viewCFTSAction.do?viewMode=searchOpened)
# ---------------------------------------------------------------------------

OPENED_COLUMN_COUNT = 12


def parse_opened_page(html: str) -> list[dict]:
    """Returns raw rows from the "opened bid details" table, one dict per
    tender. Raises `UnexpectedShape` if the column count doesn't match what
    was observed during recon (12: #, Title, Reference number, PE, Info,
    Bids submission deadline, Procedure, Status, Opened bids, Tender
    opening record, Award date, Estimated total contract value)."""
    rows = _find_table_rows(html)
    out = []
    for tr in rows:
        cells = tr.find_all("td", recursive=False)
        if len(cells) != OPENED_COLUMN_COUNT:
            raise UnexpectedShape(
                f"'opened' row has {len(cells)} columns, expected {OPENED_COLUMN_COUNT}: "
                f"{[c.get_text(strip=True)[:40] for c in cells]}"
            )
        (
            rank_cell,
            title_cell,
            ref_cell,
            pe_cell,
            info_cell,
            deadline_cell,
            procedure_cell,
            status_cell,
            opened_bids_cell,
            opening_record_cell,
            award_date_cell,
            contract_value_cell,
        ) = cells

        title_href = _link_href(title_cell)
        info_img = info_cell.find("img")
        description = info_img.get("title") if info_img and info_img.has_attr("title") else None

        out.append(
            {
                "resourceId": _resource_id(title_href),
                "title": _text(title_cell) or None,
                "referenceNumber": _text(ref_cell) or None,
                "procuringEntity": _text(pe_cell) or None,
                "description": description,
                "submissionDeadline": _text(deadline_cell) or None,
                "procedure": _text(procedure_cell) or None,
                "status": _text(status_cell) or None,
                "openedBidsUrl": _link_href(opened_bids_cell),
                "tenderOpeningRecord": _text(opening_record_cell) or None,
                "awardDate": _text(award_date_cell) or None,
                "estimatedContractValue": _text(contract_value_cell) or None,
                "listRank": _text(rank_cell) or None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# "Contract Award Notices" listing (viewCaNotices.do)
# ---------------------------------------------------------------------------

AWARDED_COLUMN_COUNT = 7


def parse_awarded_page(html: str) -> list[dict]:
    """Returns raw rows from the "Contract Award Notices" table, one dict
    per awarded contract. Raises `UnexpectedShape` if the column count
    doesn't match what was observed during recon (7: #, Procurement Method,
    PE, Title, Contract amount, Date, Notice PDF)."""
    rows = _find_table_rows(html)
    out = []
    for tr in rows:
        cells = tr.find_all("td", recursive=False)
        if len(cells) != AWARDED_COLUMN_COUNT:
            raise UnexpectedShape(
                f"'awarded' row has {len(cells)} columns, expected {AWARDED_COLUMN_COUNT}: "
                f"{[c.get_text(strip=True)[:40] for c in cells]}"
            )
        (
            rank_cell,
            method_cell,
            pe_cell,
            title_cell,
            amount_cell,
            date_cell,
            pdf_cell,
        ) = cells

        title_href = _link_href(title_cell)

        out.append(
            {
                "resourceId": _resource_id(title_href),
                "procurementMethod": _text(method_cell) or None,
                "procuringEntity": _text(pe_cell) or None,
                "title": _text(title_cell) or None,
                "contractAmount": _text(amount_cell) or None,
                "datePublished": _text(date_cell) or None,
                "noticePdfUrl": _link_href(pdf_cell),
                "listRank": _text(rank_cell) or None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# "View opened bids" per-tender bidder list (optional enrichment)
# ---------------------------------------------------------------------------

def parse_bidders_page(html: str) -> list[dict]:
    """Returns the bidder/supplier list from a `showDetailsOpenedTender.do`
    page: envelope type, supplier name, internal bid id, and financial
    value (often blank/sealed). Returns an empty list (not an error) if the
    page legitimately has no bidder table yet -- that's a normal state for
    a tender that hasn't reached bid opening."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="T01")
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        return []
    out = []
    for tr in tbody.find_all("tr", recursive=False):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        out.append(
            {
                "envelope": _text(cells[0]) or None,
                "supplierName": _text(cells[1]) or None,
                "bidId": _text(cells[2]) or None,
                "financialValueJMD": _text(cells[3]) or None,
            }
        )
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
