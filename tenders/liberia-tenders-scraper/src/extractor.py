"""Parsing logic for Liberia's e-GP (eprocurement.ppcc.gov.lr) pages.

Three listing views (see constants.LIST_CONFIGS) share the same table shell
(`<table id="T01">`) but have different columns -- header cells are matched
by their exact visible label text (not fixed column index), so a future
column-reorder on the platform's side doesn't silently scramble fields; a
column this actor relies on going missing raises UnexpectedShape instead of
returning wrong data under the old field name.

NOTE: on the "current" listing, the column literally labelled "Process No"
does NOT hold a process/reference number -- it holds the tender title (with
the link to the detail page). This is a mislabeled header upstream (verified
against the raw HTML, not a parsing bug here) -- the field is still exposed
as `title` in the output, matching what it actually contains.

The tender-detail page (`prepareViewCfTWS.do`) has no fixed field set at
all -- it's a `<dl class="row no-gutters">` of label/value pairs (Bootstrap
markup; a newer UI than GHANEPS's `dl.Grid` but the same dt/dd structure)
that varies by procurement type. That page is parsed generically: each
`<dt>` label is slugified into a camelCase key and paired with its `<dd>`
value, so new upstream fields automatically flow through (raw-passthrough)
instead of being dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESOURCE_ID_RE = re.compile(r"resourceId=(\d+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resource_id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    m = RESOURCE_ID_RE.search(href)
    return m.group(1) if m else None


def _abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return f"https://eprocurement.ppcc.gov.lr{href}"


def _cell_text(td) -> str | None:
    text = td.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _cell_link(td) -> tuple[str | None, str | None]:
    """Returns (text, href) of the first <a> in a cell, or (None, None)."""
    a = td.find("a")
    if a is None:
        return None, None
    href = a.get("href")
    text = a.get_text(strip=True) or None
    return text, href


# ---------------------------------------------------------------------------
# Listing pages
# ---------------------------------------------------------------------------


def _parse_table_shell(html_text: str, list_type: str):
    """Returns (soup, table, header_index, total_available, widget_id) or
    raises UnexpectedShape. header_index maps exact header label -> column
    index."""
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.select_one("table#T01")
    if table is None:
        raise UnexpectedShape(f"[{list_type}] no table#T01 found -- page shape has likely changed")

    header_cells = table.select("thead th")
    header_index: dict[str, int] = {}
    for i, th in enumerate(header_cells):
        label = th.get_text(strip=True)
        if label:
            header_index[label] = i

    # The number sits inside its own <strong> tag right before the label,
    # e.g. "<strong>29</strong> results in total." -- tolerate the closing
    # tag (and any whitespace) between the digits and the label text.
    count_match = re.search(r"([\d,]+)\s*(?:</strong>)?\s*results in total", html_text)
    total_available = int(count_match.group(1).replace(",", "")) if count_match else None

    widget_match = re.search(r"d-(\d+)-(?:s|p|n|o)=", html_text)
    widget_id = widget_match.group(1) if widget_match else None

    return soup, table, header_index, total_available, widget_id


def _require_columns(header_index: dict, required: list[str], list_type: str):
    missing = [c for c in required if c not in header_index]
    if missing:
        raise UnexpectedShape(
            f"[{list_type}] expected column(s) {missing} not found in header {list(header_index)} -- "
            "page shape has likely changed"
        )


def parse_current_page(html_text: str) -> dict:
    soup, table, hidx, total_available, widget_id = _parse_table_shell(html_text, "current")
    required = [
        "Process No",
        "PE",
        "Bids Submission Deadline",
        "Procedure",
        "Status",
        "Publication Date",
    ]
    _require_columns(hidx, required, "current")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        # NOTE: the "Process No" column actually holds the tender title +
        # detail link, not a reference number -- see module docstring.
        title_text, title_href = _cell_link(tds[hidx["Process No"]])
        info_idx = hidx.get("Info")
        description = None
        if info_idx is not None:
            img = tds[info_idx].find("img")
            description = img.get("title") if img else None
        notice_idx = hidx.get("Notice PDF")
        _, notice_href = _cell_link(tds[notice_idx]) if notice_idx is not None else (None, None)
        rows.append(
            {
                "resourceId": _resource_id_from_href(title_href),
                "tenderUrl": _abs_url(title_href),
                "title": title_text,
                "procuringEntity": _cell_text(tds[hidx["PE"]]),
                "description": description,
                "bidsSubmissionDeadline": _cell_text(tds[hidx["Bids Submission Deadline"]]),
                "procedure": _cell_text(tds[hidx["Procedure"]]),
                "status": _cell_text(tds[hidx["Status"]]),
                "noticePdfUrl": _abs_url(notice_href),
                "publicationDate": _cell_text(tds[hidx["Publication Date"]]),
            }
        )
    return {"rows": rows, "totalAvailable": total_available, "widgetId": widget_id}


def parse_opened_page(html_text: str) -> dict:
    soup, table, hidx, total_available, widget_id = _parse_table_shell(html_text, "opened")
    required = [
        "Subject of Process",
        "PE",
        "Bids Submission Deadline",
        "Procurement method",
        "Status",
    ]
    _require_columns(hidx, required, "opened")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        title_text, title_href = _cell_link(tds[hidx["Subject of Process"]])
        opened_idx = hidx.get("Opened Bids")
        opened_text, opened_href = _cell_link(tds[opened_idx]) if opened_idx is not None else (None, None)
        award_idx = hidx.get("Award Date")
        rows.append(
            {
                "resourceId": _resource_id_from_href(title_href),
                "tenderUrl": _abs_url(title_href),
                "title": title_text,
                "procuringEntity": _cell_text(tds[hidx["PE"]]),
                "bidsSubmissionDeadline": _cell_text(tds[hidx["Bids Submission Deadline"]]),
                "procurementMethod": _cell_text(tds[hidx["Procurement method"]]),
                "openedBidsUrl": _abs_url(opened_href),
                "openedBidsLabel": opened_text,
                "awardDate": _cell_text(tds[award_idx]) if award_idx is not None else None,
                "status": _cell_text(tds[hidx["Status"]]),
            }
        )
    return {"rows": rows, "totalAvailable": total_available, "widgetId": widget_id}


def parse_awarded_page(html_text: str) -> dict:
    soup, table, hidx, total_available, widget_id = _parse_table_shell(html_text, "awarded")
    required = ["Title", "Procuring Entity", "Provider Name", "Award Date", "Award amount"]
    _require_columns(hidx, required, "awarded")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        title_text, title_href = _cell_link(tds[hidx["Title"]])
        notice_idx = hidx.get("Notice PDF")
        _, notice_href = _cell_link(tds[notice_idx]) if notice_idx is not None else (None, None)
        package_idx = hidx.get("Package Number Code")
        grant_idx = hidx.get("Grant or Loan Number")
        lot_idx = hidx.get("Lot Name")
        rows.append(
            {
                "resourceId": _resource_id_from_href(title_href),
                "tenderUrl": _abs_url(title_href),
                "title": title_text,
                "procuringEntity": _cell_text(tds[hidx["Procuring Entity"]]),
                "supplierName": _cell_text(tds[hidx["Provider Name"]]),
                "awardDate": _cell_text(tds[hidx["Award Date"]]),
                "awardAmount": _cell_text(tds[hidx["Award amount"]]),
                "packageNumberCode": _cell_text(tds[package_idx]) if package_idx is not None else None,
                "grantOrLoanNumber": _cell_text(tds[grant_idx]) if grant_idx is not None else None,
                "lotName": _cell_text(tds[lot_idx]) if lot_idx is not None else None,
                "noticePdfUrl": _abs_url(notice_href),
            }
        )
    return {"rows": rows, "totalAvailable": total_available, "widgetId": widget_id}


LIST_PARSERS = {
    "current": parse_current_page,
    "opened": parse_opened_page,
    "awarded": parse_awarded_page,
}


def build_list_record(list_type: str, row: dict, total_available: int | None, page: int) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": f"S1-{list_type}-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": f"TENDER_{list_type.upper()}",
        "_page": page,
        "_totalAvailable": total_available,
        **row,
    }


# ---------------------------------------------------------------------------
# Tender detail page
# ---------------------------------------------------------------------------


def _slugify_label(label: str) -> str:
    label = label.replace("\xa0", " ").strip()
    if label.endswith(":"):
        label = label[:-1]
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


def parse_detail_page(html_text: str, final_url: str) -> dict:
    """Returns {"kind": "details", "fields": {...}} or {"kind": "not_found"}.

    "not_found" covers a resourceId that redirects to the platform's CAS
    login page (`/cas/login?...`) -- observed only for resourceIds outside
    the range ever surfaced by the public listing pages (tested with
    resourceId=1), never for one actually reachable from them (tested with
    ids straight off the current/opened/awarded listings, including a
    17-month-old awarded contract). This is NOT a general login wall on
    viewing -- see CRAWLING_METHOD.md.
    """
    if "/cas/login" in final_url:
        return {"kind": "not_found"}

    soup = BeautifulSoup(html_text, "lxml")

    dl = soup.select_one("dl.row") or soup.select_one("dl.Grid")
    if dl is None:
        raise UnexpectedShape("no dl.row/dl.Grid found on tender detail page -- page shape has likely changed")

    pairs = dl.find_all(["dt", "dd"], recursive=False)
    if len(pairs) % 2 != 0:
        raise UnexpectedShape(f"detail dl has an odd number ({len(pairs)}) of dt/dd children -- can't pair them safely")

    fields: dict = {}
    for i in range(0, len(pairs), 2):
        dt, dd = pairs[i], pairs[i + 1]
        if dt.name != "dt" or dd.name != "dd":
            raise UnexpectedShape(f"detail dl children out of dt/dd order at position {i} -- page shape has likely changed")
        label = dt.get_text(" ", strip=True)
        key = _slugify_label(label)
        base_key = key
        n = 2
        while key in fields:
            key = f"{base_key}{n}"
            n += 1
        value = dd.get_text(" ", strip=True) or None
        fields[key] = value
        a = dd.find("a")
        if a is not None and a.get("href"):
            fields[f"{key}Url"] = _abs_url(a["href"])

    return {"kind": "details", "fields": fields}


RESERVED_DETAIL_KEYS = {"_input", "_source", "_scrapedAt", "recordType", "resourceId", "tenderUrl"}


def build_detail_record(resource_id: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(resource_id, "not_found_or_restricted")
    fields = parsed["fields"]
    # The detail page's own "Resource ID:" dt/dd pair (value like
    # "procurement-250740") would otherwise collide with -- and silently
    # overwrite -- this actor's own numeric `resourceId` key (used for URL
    # construction and as `_input` elsewhere). Renamed rather than dropped,
    # per the raw-passthrough convention.
    safe_fields = {
        (f"{k}FromDetailPage" if k in RESERVED_DETAIL_KEYS else k): v for k, v in fields.items()
    }
    return {
        "_input": resource_id,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "resourceId": resource_id,
        "tenderUrl": f"https://eprocurement.ppcc.gov.lr/epps/cft/prepareViewCfTWS.do?resourceId={resource_id}",
        **safe_fields,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
