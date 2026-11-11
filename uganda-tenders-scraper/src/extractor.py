"""Parsing + raw-passthrough record builders for EGP Uganda.

Two very different upstream shapes feed this actor:

1. **Live "currently open" notices** -- scraped from a plain server-rendered
   HTML `<table>` (the `#procurement` tab on `/bid-notices`). No JSON API
   exists for this list (see `constants.py`).
2. **Archived (closed) notices** -- a genuine JSON REST-ish response from a
   DataTables server-side-processing AJAX endpoint. Mostly clean fields,
   plus six redundant HTML-fragment fields meant for the site's own UI
   rendering (dropped here -- see the module docstring in `constants.py`
   and "Gotcha: dropped HTML-rendering fields" in `CRAWLING_METHOD.md`).

Both are normalized into the same dataset envelope (`_input`/`_source`/
`_scrapedAt`) with upstream's own field names passed through unchanged
wherever upstream already returns clean data.
"""

import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NOTICE_ID_RE = re.compile(r"/index/(\d+)_egp")
BID_OPENING_ID_RE = re.compile(r"/bid/notice/(\d+)/opening/details")

# The six DataTables-rendering fields returned by the archived-notices AJAX
# endpoint that duplicate other clean fields in the same record, wrapped in
# HTML markup meant for the site's own UI. See CRAWLING_METHOD.md.
_ARCHIVED_HTML_NOISE_FIELDS = (
    "procuring_entity",
    "type",
    "procurement_subject",
    "published_date",
    "deadline_date",
    "action_links",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(node) -> str | None:
    if node is None:
        return None
    t = node.get_text(strip=True)
    return t or None


# ---------------------------------------------------------------------------
# Live "currently open" notices (HTML table scrape)
# ---------------------------------------------------------------------------


def parse_latest_open_notices(bid_notices_html: str) -> list[dict]:
    soup = BeautifulSoup(bid_notices_html, "html.parser")
    tab = soup.find(id="procurement")
    if tab is None:
        raise RuntimeError("`#procurement` tab not found on /bid-notices -- page shape may have changed")
    rows = tab.select("table tbody tr")
    items = []
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        entity_cell, category_cell, subject_cell, published_cell, deadline_cell = cells[:5]
        link = entity_cell.select_one("a.font-weight-semibold")
        if link is None:
            continue
        href = link.get("href", "")
        m = NOTICE_ID_RE.search(href)
        notice_id = m.group(1) if m else None
        procurement_ref = next(link.stripped_strings, None)
        entity_div = link.select_one("div.text-muted")
        procuring_entity = _text(entity_div)
        items.append(
            {
                "notice_id": notice_id,
                "detail_url": href or None,
                "procurement_ref": procurement_ref,
                "procuring_entity": procuring_entity,
                "category": _text(category_cell),
                "subject_of_procurement": _text(subject_cell),
                "published_date": _text(published_cell),
                "deadline_date": _text(deadline_cell),
            }
        )
    return items


def parse_notice_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one(".text-center.bg-dark h1")
    notice_type = _text(heading)

    ref_number = None
    full_subject = None
    ref_table = soup.find("th", string=re.compile("Procurement Ref Number"))
    if ref_table is not None:
        table = ref_table.find_parent("table")
        data_row = table.select_one("tbody tr")
        if data_row is not None:
            tds = data_row.find_all("td")
            if len(tds) >= 3:
                ref_number = _text(tds[1])
                full_subject = _text(tds[2])

    description = None
    dear_tag = soup.find(string=re.compile(r"Dear All Supplier"))
    if dear_tag is not None:
        dear_p = dear_tag.find_parent("p")
        if dear_p is not None:
            body_p = dear_p.find_next_sibling("p")
            description = _text(body_p)

    return {
        "notice_type": notice_type,
        "procurement_ref_detail": ref_number,
        "full_subject_of_procurement": full_subject,
        "description": description,
    }


# ---------------------------------------------------------------------------
# Bid-opening result detail (opportunistic enrichment)
# ---------------------------------------------------------------------------


def parse_bid_opening_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def kv(label: str) -> str | None:
        th = soup.find("th", string=re.compile(re.escape(label)))
        if th is None:
            return None
        td = th.find_next_sibling("td")
        return _text(td)

    bidders = []
    header = soup.find(string=re.compile("PARTICULARS OF BID OPENING"))
    if header is not None:
        section = header.find_parent("div")
        table = section.find_next("table") if section is not None else None
        if table is not None:
            for row in table.select("tbody tr"):
                tds = row.find_all("td")
                if len(tds) < 4:
                    continue
                bidders.append(
                    {
                        "bidder_name_address": _text(tds[1]),
                        "submission_date": _text(tds[2]),
                        "amount": _text(tds[3]),
                    }
                )

    return {
        "procurement_method": kv("Procurement Method"),
        "bid_opening_datetime": kv("Date and Time of bid Opening"),
        "bids_received": kv("Bids received"),
        "bidders": bidders,
    }


# ---------------------------------------------------------------------------
# Archived notices (AJAX JSON -- raw passthrough minus HTML-rendering noise)
# ---------------------------------------------------------------------------


def clean_archived_record(raw: dict) -> dict:
    href_blob = raw.get("procuring_entity") or raw.get("action_links") or ""
    m = NOTICE_ID_RE.search(href_blob) or BID_OPENING_ID_RE.search(href_blob)
    notice_id = m.group(1) if m else None

    # Upstream's own raw JSON string fields (e.g. `procurement_name`, `body`)
    # come back HTML-entity-escaped (e.g. "Planning &amp; Economic..."), the
    # same escaping their Blade templates apply -- decoded here for
    # readability, not a semantic rename (numbers/None/other types untouched).
    cleaned = {
        k: (html.unescape(v) if isinstance(v, str) else v)
        for k, v in raw.items()
        if k not in _ARCHIVED_HTML_NOISE_FIELDS
    }
    cleaned["notice_id"] = notice_id
    cleaned["detail_url"] = f"https://egpuganda.go.ug/index/{notice_id}_egp" if notice_id else None
    return cleaned


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------


def build_record(mode: str, source: str, fields: dict, warning: str | None = None) -> dict:
    record = {
        "_mode": mode,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **fields,
    }
    if warning:
        record["_warning"] = warning
    return record


def extract_error(mode: str, input_ref: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_mode": mode,
        "_input": input_ref,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
