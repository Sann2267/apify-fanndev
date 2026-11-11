"""Parsing logic for www.eprocure.gov.bd's three HTML-fragment endpoints.

None of these fragments carry JSON or even a full `<table>` wrapper (the
site's own JS inserts the raw `<tr>...</tr>` sequence directly into an
existing page's table via jQuery `.after()`) -- everything here is parsed
straight off the row/cell structure. Columns are matched by position
(count-checked, so a shape change raises `UnexpectedShape` rather than
silently mislabeling data) since, unlike Nepal's `dashBoardBidResult`
table, these fragments have no `<thead>` of their own to match header text
against.
"""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

LIST_ROW_COLUMNS = 6
AWARDED_ROW_COLUMNS = 8


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


def _lines(cell: Tag) -> list[str]:
    """Splits a <td> on its own <br> tags into normalized, non-empty text
    lines (site convention throughout: multi-value cells are <br>-separated,
    not comma-separated)."""
    return [_norm(p) for p in cell.get_text("\n").split("\n") if _norm(p)]


def _has_no_record_found(soup: BeautifulSoup) -> bool:
    return soup.find(id="noRecordFound") is not None


def _total_pages(soup: BeautifulSoup) -> int | None:
    tag = soup.find("input", id="totalPages")
    if tag is None or not tag.get("value", "").isdigit():
        return None
    return int(tag["value"])


# ---------------------------------------------------------------------------
# Live/open tenders (TenderDetailsServlet, funName=AllTenders)
# ---------------------------------------------------------------------------


def parse_list_fragment(html_text: str) -> dict:
    """Returns {"rows": [...], "totalPages": int|None}."""
    soup = BeautifulSoup(html_text, "html.parser")
    if _has_no_record_found(soup):
        return {"rows": [], "totalPages": 0}

    trs = [tr for tr in soup.find_all("tr") if any((c or "").startswith("bgColor") for c in (tr.get("class") or []))]
    if not trs:
        raise UnexpectedShape("no data rows (bgColor-* <tr>) and no #noRecordFound marker -- page shape has likely changed")

    rows = []
    for tr in trs:
        tds = tr.find_all("td", recursive=False)
        if len(tds) != LIST_ROW_COLUMNS:
            raise UnexpectedShape(f"expected {LIST_ROW_COLUMNS} <td> in a tender row, got {len(tds)}")

        id_lines = _lines(tds[1])
        tender_id = id_lines[0].rstrip(",") if id_lines else None
        ref_no, ref_date = None, None
        if len(id_lines) > 1:
            ref_part = id_lines[1].rstrip(",")
            # Observed both ", Dated: DD-Mon-YYYY" and ", Date: DD-MM-YY" --
            # the procuring entity types this reference number by hand, so
            # its trailing-date convention is not consistent site-wide.
            m = re.search(r", Dated?: (.+)$", ref_part)
            if m:
                ref_no, ref_date = ref_part[: m.start()], m.group(1)
            else:
                ref_no = ref_part
        status = id_lines[2] if len(id_lines) > 2 else None

        cat_lines = _lines(tds[2])
        procurement_nature = cat_lines[0].rstrip(",") if cat_lines else None
        brief_span = tds[2].find("span", id=re.compile(r"^tenderBrief_\d+$"))
        project_title = _norm(brief_span.get_text(" ", strip=True)) if brief_span else None

        entity_lines = [ln.rstrip(",") for ln in _lines(tds[3])]
        type_lines = [ln.rstrip(",") for ln in _lines(tds[4])]
        date_lines = [ln.rstrip(",") for ln in _lines(tds[5])]

        rows.append(
            {
                "tenderId": tender_id,
                "tenderUrl": (f"https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id={tender_id}&h=t" if tender_id else None),
                "referenceNo": ref_no,
                "referenceDate": ref_date,
                "status": status,
                "procurementNature": procurement_nature,
                "projectTitle": project_title,
                "procuringEntity": " / ".join(entity_lines) or None,
                "procurementType": " / ".join(type_lines) or None,
                "noticePublishDate": date_lines[0] if len(date_lines) > 0 else None,
                "bidClosingDate": date_lines[1] if len(date_lines) > 1 else None,
            }
        )
    return {"rows": rows, "totalPages": _total_pages(soup)}


def build_list_record(row: dict, total_pages: int | None, query_label: str) -> dict:
    return {
        "_input": query_label,
        "_source": "S1-list",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_LIST",
        "_totalPages": total_pages,
        **row,
    }


# ---------------------------------------------------------------------------
# Awarded contracts / Notice of Award (SearchNoaServlet)
# ---------------------------------------------------------------------------


def parse_awarded_fragment(html_text: str) -> dict:
    """Returns {"rows": [...], "totalPages": int|None}."""
    soup = BeautifulSoup(html_text, "html.parser")
    if _has_no_record_found(soup):
        return {"rows": [], "totalPages": 0}

    trs = [tr for tr in soup.find_all("tr") if any((c or "").startswith("bgColor") for c in (tr.get("class") or []))]
    if not trs:
        raise UnexpectedShape("no data rows (bgColor-* <tr>) and no #noRecordFound marker -- page shape has likely changed")

    rows = []
    for tr in trs:
        tds = tr.find_all("td", recursive=False)
        if len(tds) != AWARDED_ROW_COLUMNS:
            raise UnexpectedShape(f"expected {AWARDED_ROW_COLUMNS} <td> in an awarded-contract row, got {len(tds)}")

        ministry = " / ".join(_lines(tds[1])) or None

        a = tds[2].find("a", href=True)
        tender_id, pkg_lot_id, ref_no = None, None, None
        if a is not None:
            qs = parse_qs(urlparse(a["href"]).query)
            tender_id = (qs.get("tenderid") or [None])[0]
            pkg_lot_id = (qs.get("pkgLotId") or [None])[0]
            a_text = _norm(a.get_text(" ", strip=True))
            if ", " in a_text:
                _, ref_no = a_text.split(", ", 1)
        span = tds[2].find("span", class_="more")
        description = _norm(span.get_text(" ", strip=True)) if span else None
        award_notice_date = None
        if span is not None:
            tail_parts = [sib if isinstance(sib, str) else sib.get_text(" ", strip=True) for sib in span.next_siblings]
            award_notice_date = _norm(" ".join(tail_parts)) or None

        office_lines = _lines(tds[3])
        procuring_office = office_lines[0] if office_lines else None
        procurement_method = office_lines[1] if len(office_lines) > 1 else None

        rows.append(
            {
                "tenderId": tender_id,
                "pkgLotId": pkg_lot_id,
                "awardedContractUrl": (
                    f"https://www.eprocure.gov.bd/resources/common/ViewAwardedContracts.jsp?pkgLotId={pkg_lot_id}&tenderid={tender_id}"
                    if pkg_lot_id and tender_id
                    else None
                ),
                "ministry": ministry,
                "referenceNo": ref_no,
                "packageDescription": description,
                "awardNoticeDate": award_notice_date,
                "procuringOffice": procuring_office,
                "procurementMethod": procurement_method,
                "location": _norm(tds[4].get_text(" ", strip=True)) or None,
                "publishDate": _norm(tds[5].get_text(" ", strip=True)) or None,
                "supplierName": _norm(tds[6].get_text(" ", strip=True)) or None,
                "contractValueCroreBdt": _norm(tds[7].get_text(" ", strip=True)) or None,
            }
        )
    return {"rows": rows, "totalPages": _total_pages(soup)}


def build_awarded_record(row: dict, total_pages: int | None, query_label: str) -> dict:
    return {
        "_input": query_label,
        "_source": "S1-awarded",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_AWARDED",
        "_totalPages": total_pages,
        **row,
    }


# ---------------------------------------------------------------------------
# Tender detail page (GET ViewTender.jsp?id=...)
# ---------------------------------------------------------------------------

NOT_FOUND_TEXT = "not exists or You are un-authorized"


def _parse_label_value_tables(soup: BeautifulSoup) -> dict:
    """Every info-section table on this page carries `class="formStyle_1 "`
    (basic info, key/funding info, particulars, tenderer info, procuring
    entity details); the lot table (`class="tableList_1 "`) is parsed
    separately by `_parse_lots`. Label cells (`class="ff"`) are always
    immediately followed by their value cell in the same <tr>, so pairwise
    (label, value) stepping across direct-child <td>s -- same convention as
    this vertical's Nepal actor -- reliably reconstructs every field without
    hardcoding a fixed list (raw passthrough)."""
    fields: dict = {}
    for table in soup.find_all("table", class_="formStyle_1"):
        for tr in table.find_all("tr", recursive=False):
            tds = tr.find_all("td", recursive=False)
            i = 0
            while i < len(tds) - 1:
                if "ff" in (tds[i].get("class") or []):
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


def _parse_lots(soup: BeautifulSoup) -> list[dict]:
    table = soup.find("table", class_="tableList_1")
    if table is None:
        return []
    header_row = table.find("tr")
    if header_row is None:
        return []
    keys = [_slugify_label(_norm(th.get_text(" ", strip=True))) for th in header_row.find_all("th")]
    if not keys:
        return []
    lots = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td", recursive=False)
        if len(tds) != len(keys):
            continue
        lots.append({keys[i]: _norm(tds[i].get_text(" ", strip=True)) or None for i in range(len(keys))})
    return lots


def parse_detail(html_text: str) -> dict:
    """Returns {"kind": "details", "fields": {...}, "lots": [...],
    "documentsUrl": str|None} or {"kind": "not_found"}. A nonexistent
    tenderId returns HTTP 200 with an explicit human-readable "not exists"
    message rather than a 404 or a blank template -- detected directly."""
    if NOT_FOUND_TEXT in html_text:
        return {"kind": "not_found"}

    soup = BeautifulSoup(html_text, "html.parser")
    fields = _parse_label_value_tables(soup)
    if not fields:
        raise UnexpectedShape("no label/value pairs found on tender detail page -- page shape has likely changed")

    lots = _parse_lots(soup)
    doc_link = soup.find("a", class_="action-button-document")
    documents_url = f"https://www.eprocure.gov.bd{doc_link['href']}" if doc_link and doc_link.get("href") else None

    return {"kind": "details", "fields": fields, "lots": lots, "documentsUrl": documents_url}


def build_detail_record(tender_id: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(tender_id, "not_found")
    return {
        "_input": tender_id,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "tenderId": tender_id,
        "tenderUrl": f"https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id={tender_id}&h=t",
        **parsed["fields"],
        "lots": parsed["lots"],
        "documentsUrl": parsed["documentsUrl"],
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
