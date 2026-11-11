"""Parsing logic for GHANEPS pages.

Three listing views (see constants.LIST_CONFIGS) share the same table shell
(`<table id="T01">`) but have different columns -- header cells are matched
by their exact visible label text (not fixed column index), so a future
column-reorder on GHANEPS's side doesn't silently scramble fields; a column
this actor relies on going missing raises UnexpectedShape instead of
returning wrong data under the old field name.

The tender-detail page (`prepareViewCfTWS.do`) has no fixed field set at
all -- it's a `<dl class="Grid">` of label/value pairs that varies by
procurement type (RFQ vs NCT vs Framework Agreement, number of lots, etc).
That page is parsed generically: each `<dt>` label is slugified into a
camelCase key and paired with its `<dd>` value, so new upstream fields
automatically flow through (raw-passthrough) instead of being dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import LIST_CONFIGS

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

    count_match = re.search(r"([\d,]+)\s+results in total", html_text)
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
        "Tender Title",
        "Procuring Entity",
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
        title_text, title_href = _cell_link(tds[hidx["Tender Title"]])
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
                "tenderUrl": title_href,
                "title": title_text,
                "procuringEntity": _cell_text(tds[hidx["Procuring Entity"]]),
                "description": description,
                "bidsSubmissionDeadline": _cell_text(tds[hidx["Bids Submission Deadline"]]),
                "procedure": _cell_text(tds[hidx["Procedure"]]),
                "status": _cell_text(tds[hidx["Status"]]),
                "noticePdfUrl": notice_href,
                "publicationDate": _cell_text(tds[hidx["Publication Date"]]),
            }
        )
    return {"rows": rows, "totalAvailable": total_available, "widgetId": widget_id}


def parse_opened_page(html_text: str) -> dict:
    soup, table, hidx, total_available, widget_id = _parse_table_shell(html_text, "opened")
    required = [
        "CfT Title",
        "Reference number",
        "PE",
        "Bids Submission Deadline",
        "Procurement Method",
        "Status",
    ]
    _require_columns(hidx, required, "opened")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        title_text, title_href = _cell_link(tds[hidx["CfT Title"]])
        opened_idx = hidx.get("Opened Bids")
        opened_text, opened_href = _cell_link(tds[opened_idx]) if opened_idx is not None else (None, None)
        award_idx = hidx.get("Award Date")
        rows.append(
            {
                "resourceId": _resource_id_from_href(title_href),
                "tenderUrl": title_href,
                "title": title_text,
                "referenceNumber": _cell_text(tds[hidx["Reference number"]]),
                "procuringEntity": _cell_text(tds[hidx["PE"]]),
                "bidsSubmissionDeadline": _cell_text(tds[hidx["Bids Submission Deadline"]]),
                "procurementMethod": _cell_text(tds[hidx["Procurement Method"]]),
                "openedBidsUrl": opened_href,
                "openedBidsLabel": opened_text,
                "awardDate": _cell_text(tds[award_idx]) if award_idx is not None else None,
                "status": _cell_text(tds[hidx["Status"]]),
            }
        )
    return {"rows": rows, "totalAvailable": total_available, "widgetId": widget_id}


def parse_awarded_page(html_text: str) -> dict:
    soup, table, hidx, total_available, widget_id = _parse_table_shell(html_text, "awarded")
    required = ["Tender Title", "Procuring Entity", "Supplier Name", "Award Date", "Award amount"]
    _require_columns(hidx, required, "awarded")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        title_text, title_href = _cell_link(tds[hidx["Tender Title"]])
        notice_idx = hidx.get("Notice PDF")
        _, notice_href = _cell_link(tds[notice_idx]) if notice_idx is not None else (None, None)
        lot_idx = hidx.get("Lot Name")
        rows.append(
            {
                "resourceId": _resource_id_from_href(title_href),
                "tenderUrl": title_href,
                "title": title_text,
                "procuringEntity": _cell_text(tds[hidx["Procuring Entity"]]),
                "supplierName": _cell_text(tds[hidx["Supplier Name"]]),
                "awardDate": _cell_text(tds[hidx["Award Date"]]),
                "awardAmount": _cell_text(tds[hidx["Award amount"]]),
                "lotName": _cell_text(tds[lot_idx]) if lot_idx is not None else None,
                "noticePdfUrl": notice_href,
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


def parse_detail_page(html_text: str) -> dict:
    """Returns {"kind": "details", "fields": {...}} or {"kind": "not_found"}.

    "not_found" covers both a genuinely invalid resourceId and one that (per
    live testing) redirects to GHANEPS's CAS login page -- observed only for
    resourceIds outside the range ever surfaced by the public listing pages,
    never for one actually reachable from them. This is NOT the same as a
    general login wall on viewing (see CRAWLING_METHOD.md).
    """
    soup = BeautifulSoup(html_text, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and "e-PPS" in title_tag.get_text() and "GHANEPS" not in title_tag.get_text():
        return {"kind": "not_found"}

    dl = soup.select_one("dl.Grid")
    if dl is None:
        raise UnexpectedShape("no dl.Grid found on tender detail page -- page shape has likely changed")

    pairs = dl.find_all(["dt", "dd"], recursive=False)
    if len(pairs) % 2 != 0:
        raise UnexpectedShape(f"dl.Grid has an odd number ({len(pairs)}) of dt/dd children -- can't pair them safely")

    fields: dict = {}
    for i in range(0, len(pairs), 2):
        dt, dd = pairs[i], pairs[i + 1]
        if dt.name != "dt" or dd.name != "dd":
            raise UnexpectedShape(f"dl.Grid children out of dt/dd order at position {i} -- page shape has likely changed")
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
            fields[f"{key}Url"] = a["href"]

    header = soup.select_one("div.ExtraInfo div.ContextMenu")
    tender_header_title = None
    if header is not None:
        strong = header.find("strong")
        tender_header_title = strong.get_text(strip=True) if strong else None

    return {"kind": "details", "fields": fields, "tenderHeaderTitle": tender_header_title}


def build_detail_record(resource_id: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(resource_id, "not_found_or_restricted")
    return {
        "_input": resource_id,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "resourceId": resource_id,
        "tenderUrl": f"https://www.ghaneps.gov.gh/epps/cft/prepareViewCfTWS.do?resourceId={resource_id}",
        "tenderHeaderTitle": parsed.get("tenderHeaderTitle"),
        **parsed["fields"],
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
