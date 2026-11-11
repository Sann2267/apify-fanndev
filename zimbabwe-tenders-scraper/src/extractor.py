"""Parse PRAZ eGP System (egp.praz.org.zw) HTML into dataset-ready records.

There is no JSON API anywhere in this flow (see CRAWLING_METHOD.md) -- every
record is derived from server-rendered HTML tables/label-value blocks. Per
this portfolio's raw-passthrough convention (.ai/conventions/dataset-envelope.md)
field labels are kept as close to the site's own wording as possible: table
column headers (read live from <thead>, not hardcoded) and detail-page
<label>/<b> field labels are turned into camelCase keys programmatically, so
a label the site adds later still flows through instead of being silently
dropped.

Known site quirk: several listing tables' `data-label="..."` attributes on
<td> cells do NOT match their own <thead> column (confirmed live on the Live
Tenders table -- e.g. a cell holding the tender's reference number carries
`data-label="Control Number"`, and the cell holding the title carries
`data-label="Tender Reference Number"`). This extractor therefore keys every
row by **column position against the real <thead> headers**, never by the
(unreliable) data-label attribute.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

TENDER_DETAIL_ID_RE = re.compile(r"viewLiveTenderDetails/(\d+)")
AWARD_DETAIL_ID_RE = re.compile(r"viewAwardNotice/(\d+)")
SUMMARY_REPORT_ID_RE = re.compile(r"viewSummaryReport/(\d+)")
PAGINATION_RE = re.compile(
    r"Page\s+([\d,]+)\s+of\s+([\d,]+),\s*showing\s+([\d,]+)\s*record\(s\)\s*out of\s+([\d,]+)\s*total",
    re.IGNORECASE,
)


class UnexpectedShape(Exception):
    """Raised when a page that returned HTTP 200 doesn't contain the HTML
    structure this actor expects (listing table, detail label block) --
    signals a site redesign rather than a normal empty-result page. See
    .ai/CLAUDE.md principle #6: fail loud, never emit a silently-empty
    "success" record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label_to_key(label: str) -> str:
    """'Required Supplier Category Code' -> 'requiredSupplierCategoryCode'.
    Strips punctuation/parentheses, camelCases on whitespace."""
    label = label.replace("\xa0", " ")
    words = re.findall(r"[A-Za-z0-9]+", label)
    if not words:
        return "field"
    first, *rest = words
    return first.lower() + "".join(w[:1].upper() + w[1:].lower() for w in rest)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def parse_pagination_info(html: str) -> dict | None:
    """Parses the CakePHP paginator's "Page X of Y, showing Z record(s) out
    of N total" footer text. Returns None when absent (e.g. Award Notices,
    which -- confirmed live -- renders no such footer and ignores the
    ?page= param entirely; see CRAWLING_METHOD.md)."""
    m = PAGINATION_RE.search(html)
    if not m:
        return None
    return {
        "currentPage": _num(m.group(1)),
        "totalPages": _num(m.group(2)),
        "pageSize": _num(m.group(3)),
        "totalRecords": _num(m.group(4)),
    }


def _find_listing_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        classes = table.get("class") or []
        if "table-bordered" in classes and "table-hover" in classes:
            return table
    return None


def parse_listing_table(html: str, id_re: re.Pattern) -> list[dict]:
    """Generic parser for the three bulletin-board listing tables (Live
    Tenders, Former Opportunities, Award Notices). Columns are read live
    from the header row (the first <tr> containing <th> cells) and data
    rows are every <tr> that follows it, built strictly by position (see
    module docstring re: unreliable data-label attributes).

    NOTE: does NOT rely on `<thead>`/`find_parent("thead")` -- the Former
    Opportunities page ships a confirmed markup bug (two nested `<thead>`
    open tags but only one `</thead>` close tag), which makes lxml parse
    *every* row in that table as a descendant of `<thead>`. Locating the
    header row directly and taking "every <tr> after it" sidesteps that
    bug entirely (same technique used by `_table_to_records` for the
    detail-page line-item tables)."""
    soup = BeautifulSoup(html, "lxml")
    table = _find_listing_table(soup)
    if table is None:
        raise UnexpectedShape("Listing table (table.table-bordered.table-hover) not found")

    header_tr = None
    headers: list[str] = []
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths:
            header_tr = tr
            headers = [th.get_text(" ", strip=True) for th in ths]
            break
    if header_tr is None or not headers:
        raise UnexpectedShape("Listing table has no header row (<tr> containing <th> cells)")
    keys = [_label_to_key(h) for h in headers]

    body_trs = []
    started = False
    for tr in table.find_all("tr"):
        if tr is header_tr:
            started = True
            continue
        if started:
            body_trs.append(tr)
    rows = []
    for tr in body_trs:
        tds = tr.find_all("td")
        if not tds:
            continue
        if len(tds) != len(keys):
            raise UnexpectedShape(
                f"Row has {len(tds)} cells, expected {len(keys)} (headers={headers})"
            )
        row: dict = {}
        for key, td in zip(keys, tds):
            row[key] = td.get_text(" ", strip=True)

        first_link = tds[0].find("a")
        if first_link and first_link.get("href"):
            m = id_re.search(first_link["href"])
            if m:
                row["_id"] = m.group(1)
                row["_detailHref"] = first_link["href"]

        for td in tds:
            a = td.find("a")
            if a and a.get("href"):
                sm = SUMMARY_REPORT_ID_RE.search(a["href"])
                if sm:
                    row["summaryReportUrl"] = a["href"]

        rows.append(row)
    return rows


def parse_live_tenders(html: str) -> tuple[list[dict], dict | None]:
    rows = parse_listing_table(html, TENDER_DETAIL_ID_RE)
    pagination = parse_pagination_info(html)
    return rows, pagination


def parse_former_tenders(html: str) -> tuple[list[dict], dict | None]:
    rows = parse_listing_table(html, TENDER_DETAIL_ID_RE)
    pagination = parse_pagination_info(html)
    return rows, pagination


def parse_award_notices(html: str) -> tuple[list[dict], dict | None]:
    rows = parse_listing_table(html, AWARD_DETAIL_ID_RE)
    pagination = parse_pagination_info(html)
    return rows, pagination


def _table_to_records(table) -> list[dict] | None:
    """Parses a sub-table that has a real header row (<th> cells) into a
    list of dicts -- used for the "Line Item Details" breakdown table
    embedded in both tender and award detail pages. Rows whose cell count
    doesn't match the header are skipped (not raised) -- this is optional
    enrichment, not the primary record."""
    header_tr = None
    headers: list[str] = []
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths:
            header_tr = tr
            headers = [th.get_text(" ", strip=True) for th in ths]
            break
    if header_tr is None:
        return None
    keys = [_label_to_key(h) for h in headers]

    records = []
    started = False
    for tr in table.find_all("tr"):
        if tr is header_tr:
            started = True
            continue
        if not started:
            continue
        tds = tr.find_all("td")
        if not tds or len(tds) != len(keys):
            continue
        records.append({k: td.get_text(" ", strip=True) for k, td in zip(keys, tds)})
    return records or None


def _label_value_pairs(container: Tag) -> list[tuple[str, str]]:
    """Walks every <label> and field-style <b> tag (text ending in ':') in
    document order and pairs it with its value -- either inline (e.g.
    "Tender Id :46190") or gathered from following sibling text/tags up to
    the next label/bold-field or a <table> boundary. Comment nodes (the site
    ships several HTML-commented-out label rows) are skipped explicitly."""
    pairs: list[tuple[str, str]] = []
    for tag in container.find_all(["label", "b"]):
        raw_text = tag.get_text(" ", strip=True)
        if ":" not in raw_text:
            continue
        label_part, _, inline_value = raw_text.partition(":")
        label_part = label_part.strip()
        if not label_part or len(label_part) > 80:
            continue
        inline_value = inline_value.strip()
        if inline_value:
            value = inline_value
        else:
            parts = []
            for sib in tag.next_siblings:
                if isinstance(sib, Comment):
                    continue
                if isinstance(sib, Tag):
                    if sib.name in ("label", "b", "table"):
                        break
                    txt = sib.get_text(" ", strip=True)
                elif isinstance(sib, NavigableString):
                    txt = str(sib).strip()
                else:
                    continue
                if txt:
                    parts.append(txt)
            value = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if value:
            pairs.append((label_part, value))
    return pairs


def parse_detail_page(html: str) -> dict:
    """Parses a tender detail page (`Indexes/viewLiveTenderDetails/<id>`) or
    an award notice detail page (`Indexes/viewAwardNotice/<id>`) -- both use
    the same #block_content label/value layout. Field count/labels vary by
    record type and by tender class (goods/works/services/consultancy) --
    confirmed live (a goods tender had 20 label fields plus a line-item
    table; an award notice had a similar set plus awardee/contract-amount
    fields), so every label is turned into a key dynamically rather than
    matching a fixed list."""
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", id="block_content")
    if container is None:
        raise UnexpectedShape("Detail page content block (div#block_content) not found")

    pairs = _label_value_pairs(container)
    if not pairs:
        raise UnexpectedShape("Detail page has no <label>/<b> field pairs in #block_content")

    fields: dict = {}
    raw_fields = []
    for label, value in pairs:
        key = _label_to_key(label)
        fields[key] = value
        raw_fields.append({"label": label, "value": value})

    line_items = None
    for table in container.find_all("table"):
        records = _table_to_records(table)
        if records:
            line_items = records
            break

    result: dict = {"fields": fields, "rawFields": raw_fields}
    if line_items:
        result["lineItems"] = line_items
    return result


def build_list_record(query: str, source: str, row: dict) -> dict:
    row = dict(row)
    _id = row.pop("_id", None)
    detail_href = row.pop("_detailHref", None)
    record = {
        "_input": query,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **row,
    }
    if _id:
        record["_id"] = _id
    if detail_href:
        record["_detailUrl"] = f"https://egp.praz.org.zw{detail_href}" if detail_href.startswith("/") else detail_href
    return record


def build_detail_record(query: str, source: str, id_field: str, id_value: str, detail: dict) -> dict:
    return {
        "_input": query,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        id_field: id_value,
        **detail,
    }


def build_error(query: str, error_kind: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
