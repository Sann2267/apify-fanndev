"""Parsing logic for bolpatra.gov.np's listing and tender-detail fragments.

The listing table (`table#dashBoardBidResult`, shared by both the "latest"
dashboard endpoint and the filtered search endpoint) has a fixed 9-column
header; columns are matched by exact visible header text rather than
positional index, so a future column reorder raises `UnexpectedShape`
instead of silently mislabeling data.

The tender-detail fragment (`getTenderDetails?tenderId=...`) has no JSON
field names at all -- it's a series of `<table>` label/value `<td>` pairs
across several sections (basic info, bid info, funding, schedule, fee,
contact). Per the convention established by this vertical's first actor
(`ghana-tenders-scraper`, which slugifies `<dl class="Grid">` `dt`/`dd`
pairs), this parser slugifies each label into a camelCase key generically
rather than hardcoding a fixed field list, so upstream additions/renames
flow through automatically (raw-passthrough) instead of being dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

LISTING_HEADERS = [
    "Sl. No.",
    "IFB / RFP / EOI / PQ No.",
    "Project Title",
    "Public Entity Name",
    "Procurement Type",
    "Status",
    "Notice Published Date",
    "Last Date of Bid Submission",
    "No of Days Left",
]

TENDER_ID_RE = re.compile(r"getTenderDetails\('(\d+)'\)")
TENDER_ID_IN_URL_RE = re.compile(r"tenderId=(\d+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _slugify_label(label: str) -> str:
    label = label.replace("\xa0", " ").strip()
    if label.endswith(":"):
        label = label[:-1]
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


# ---------------------------------------------------------------------------
# Listing page (searchBidDashboardHomePage / SearchOpportunitiesResultHomePage)
# ---------------------------------------------------------------------------


def parse_listing(html_text: str) -> dict:
    """Returns {"rows": [...], "totalAvailable": int|None}. Raises
    UnexpectedShape if the result table or its expected header columns are
    missing -- must NOT be silently swallowed (fail loud, per project
    convention)."""
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", id="dashBoardBidResult")
    if table is None:
        raise UnexpectedShape("no table#dashBoardBidResult found -- page shape has likely changed")

    thead = table.find("thead")
    if thead is None:
        raise UnexpectedShape("table#dashBoardBidResult has no <thead> -- page shape has likely changed")
    header_labels = [_norm(th.get_text(" ", strip=True)) for th in thead.find_all("th")]
    missing = [h for h in LISTING_HEADERS if h not in header_labels]
    if missing:
        raise UnexpectedShape(
            f"expected column(s) {missing} not found in header {header_labels} -- page shape has likely changed"
        )

    total_match = re.search(r'name="totalRecords"\s+value="(\d+)"', html_text)
    total_available = int(total_match.group(1)) if total_match else None

    rows = []
    for tr in table.find_all("tr"):
        if tr.find_parent("thead") is not None:
            continue
        tds = tr.find_all("td")
        if len(tds) != len(LISTING_HEADERS):
            continue
        a = tr.find("a", onclick=True)
        m = TENDER_ID_RE.search(a["onclick"]) if a else None
        tender_id = m.group(1) if m else None
        rows.append(
            {
                "tenderId": tender_id,
                "tenderUrl": (f"https://bolpatra.gov.np/egp/getTenderDetails?tenderId={tender_id}" if tender_id else None),
                "ifbNo": _norm(tds[1].get_text(" ", strip=True)),
                "projectTitle": _norm(tds[2].get_text(" ", strip=True)),
                "publicEntityName": _norm(tds[3].get_text(" ", strip=True)),
                "procurementType": _norm(tds[4].get_text(" ", strip=True)),
                "status": _norm(tds[5].get_text(" ", strip=True)) or None,
                "noticePublishedDate": _norm(tds[6].get_text(" ", strip=True)),
                "lastDateOfBidSubmission": _norm(tds[7].get_text(" ", strip=True)),
                "daysLeft": _norm(tds[8].get_text(" ", strip=True)) or None,
            }
        )
    return {"rows": rows, "totalAvailable": total_available}


def build_list_record(row: dict, total_available: int | None, total_returned: int, query_label: str) -> dict:
    return {
        "_input": query_label,
        "_source": "S1-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_LIST",
        "_totalAvailable": total_available,
        "_totalReturned": total_returned,
        **row,
    }


# ---------------------------------------------------------------------------
# Tender detail page (getTenderDetails?tenderId=...)
# ---------------------------------------------------------------------------

def _parse_label_value_tables(soup: BeautifulSoup) -> dict:
    """Every section table (basic info, bid info, funding, schedule, fee,
    contact) is rendered with `cellpadding="10"` -- the later document
    tables (Bid Document/Addendum/Bid Query Response/LOI, parsed separately
    by _parse_documents) use `cellpadding="1px"`, and the outer wrapper
    table around the whole "Download Documents" block has no cellpadding
    attribute at all. Matching on this attribute (rather than the nearest
    preceding <legend>, which for the outer wrapper table incorrectly
    resolves to the PRIOR section's legend since "Download Documents" is
    its own child, not a preceding sibling) reliably selects only the
    genuine label/value tables."""
    fields: dict = {}
    for table in soup.find_all("table", cellpadding="10"):
        for tr in table.find_all("tr", recursive=False):
            tds = tr.find_all("td", recursive=False)
            i = 0
            while i < len(tds) - 1:
                label = _norm(tds[i].get_text(" ", strip=True))
                if label:
                    key = _slugify_label(label)
                    base_key, n = key, 2
                    while key in fields:
                        key = f"{base_key}{n}"
                        n += 1
                    fields[key] = _norm(tds[i + 1].get_text(" ", strip=True)) or None
                i += 2
    return fields


def _parse_documents(soup: BeautifulSoup) -> dict:
    documents: dict = {}
    for fieldset in soup.find_all("fieldset"):
        legend = fieldset.find("legend")
        if legend is None:
            continue
        section_key = _slugify_label(_norm(legend.get_text(strip=True)))
        table = fieldset.find("table")
        if table is None:
            documents[section_key] = []
            continue
        items = []
        # bolpatra's own markup leaves the header <tr> unclosed, so the data
        # <tr> ends up nested INSIDE it (and an empty <tr> in between) rather
        # than as a sibling -- table.find_all("tr") must stay recursive to
        # reach it, but td lookup per-tr must NOT be recursive, or the same
        # data row's cells get double/triple-counted through each ancestor
        # <tr> the lenient parser created.
        for tr in table.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 3:
                continue  # header row, wrapper row, or "No Relevant Documents Available" (colspan row)
            a = tds[2].find("a")
            if a is None or not a.get("href"):
                continue
            items.append(
                {
                    "documentType": _norm(tds[0].get_text(" ", strip=True)),
                    "date": _norm(tds[1].get_text(" ", strip=True)),
                    "downloadUrl": f"https://bolpatra.gov.np/egp/{a['href']}",
                }
            )
        documents[section_key] = items
    return documents


def parse_detail(html_text: str) -> dict:
    """Returns {"kind": "details", "fields": {...}, "documents": {...}} or
    {"kind": "not_found"}. An invalid/unknown tenderId returns HTTP 200 with
    the exact same template but every value blank -- confirmed on a
    deliberately out-of-range id -- so an empty "Public Entity Name" is
    treated as the not-found signal."""
    soup = BeautifulSoup(html_text, "html.parser")
    if soup.find("legend") is None:
        raise UnexpectedShape("no <legend> found on tender detail fragment -- page shape has likely changed")

    fields = _parse_label_value_tables(soup)
    if not fields:
        raise UnexpectedShape("no label/value pairs found on tender detail fragment -- page shape has likely changed")
    if not fields.get("publicEntityName"):
        return {"kind": "not_found"}

    documents = _parse_documents(soup)
    return {"kind": "details", "fields": fields, "documents": documents}


def build_detail_record(tender_id: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(tender_id, "not_found")
    return {
        "_input": tender_id,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "tenderId": tender_id,
        "tenderUrl": f"https://bolpatra.gov.np/egp/getTenderDetails?tenderId={tender_id}",
        **parsed["fields"],
        **parsed["documents"],
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
