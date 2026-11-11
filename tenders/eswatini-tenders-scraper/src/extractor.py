"""Parsing logic for ESPPRA pages.

Two listing views ("tenders" / "award_intentions") share the same row shell
-- `<div class="list-item job-box">` -- but the ESPPRA site does not use
fixed table columns: each row is a title (`<h5>`) followed by a handful of
`<p>` tags, some plain text (procuring entity, reference number) and some
"Label: value" pairs (e.g. "Procurement Method: Request For Tender"). This
is parsed generically -- every "Label: value" paragraph is slugified into a
camelCase key, the same label-based philosophy already used by this
portfolio's ghana-tenders-scraper for its dt/dd detail page -- so a label
ESPPRA adds or removes in a future redesign flows straight through under its
own name (raw-passthrough) instead of quietly shifting into the wrong field.

"suspended_suppliers" is a DataTables server-side JSON endpoint (no HTML to
parse at all) -- see parse_suspended_json.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import BASE, RECORD_TYPES

JOBBOX_LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z ]{2,40}):\s*(.*)$")
TOTAL_RE = re.compile(r"Total\s+([\d,]+)\s+Record\s*:\s*(\d+)\s+Pages?", re.IGNORECASE)

# DataTables column order for api/suspendedSupplier_list.php, matched 1:1
# against suspended.php's own <thead> labels. Column 6 ("Action") is marked
# not-visible/not-searchable client-side and observed to hold a placeholder
# value ("1st Jan 70" == epoch zero) rather than real data -- passed through
# raw anyway per this project's raw-passthrough convention, documented as a
# known quirk in CRAWLING_METHOD.md / README.md.
SUSPENDED_COLUMNS = [
    "supplierId",
    "tradingName",
    "companyName",
    "suspensionStartDate",
    "suspensionEndDate",
    "suspensionDocumentFile",
    "_actionRawPlaceholder",
]


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify_label(label: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label.strip()) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


# ---------------------------------------------------------------------------
# "jobbox" listing pages (tenders, award_intentions)
# ---------------------------------------------------------------------------


def parse_jobbox_page(html_text: str, list_type: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    if soup.select_one("#post-list") is None and soup.select_one("#postContent") is None:
        raise UnexpectedShape(
            f"[{list_type}] no #post-list/#postContent container found -- page shape has likely changed"
        )

    m = TOTAL_RE.search(html_text)
    total_available = int(m.group(1).replace(",", "")) if m else None
    total_pages = int(m.group(2)) if m else None

    rows = []
    for box in soup.select("div.list-item.job-box"):
        h5 = box.find("h5")
        title = h5.get_text(strip=True) if h5 else None
        if not title:
            raise UnexpectedShape(
                f"[{list_type}] a list-item job-box has no <h5> title -- page shape has likely changed"
            )

        unlabeled: list[str] = []
        fields: dict = {}
        for p in box.find_all("p", recursive=False):
            text = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
            if not text:
                continue
            lm = JOBBOX_LABEL_RE.match(text)
            if lm:
                key = _slugify_label(lm.group(1))
                fields[key] = lm.group(2).strip() or None
            else:
                unlabeled.append(text)

        a = box.find("a", href=True)
        document_id = a.get("id") if a else None
        document_url = urljoin(f"{BASE}/", a["href"]) if a else None

        rows.append(
            {
                "title": title,
                "procuringEntity": unlabeled[0] if len(unlabeled) > 0 else None,
                "referenceNumber": unlabeled[1] if len(unlabeled) > 1 else None,
                **fields,
                "documentId": document_id,
                "documentUrl": document_url,
            }
        )

    return {"rows": rows, "totalAvailable": total_available, "totalPages": total_pages}


# ---------------------------------------------------------------------------
# "json_table" listing (suspended_suppliers)
# ---------------------------------------------------------------------------


def parse_suspended_json(raw_text: str) -> dict:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"suspended supplier API did not return valid JSON: {e!r}") from e

    if "data" not in data or not isinstance(data["data"], list):
        raise UnexpectedShape("suspended supplier API response missing a 'data' array -- shape has likely changed")

    rows = []
    for entry in data["data"]:
        if not isinstance(entry, list) or len(entry) < 6:
            raise UnexpectedShape(
                f"suspended supplier row has {len(entry) if isinstance(entry, list) else type(entry)} "
                "columns, expected >=6 -- shape has likely changed"
            )
        row = {SUSPENDED_COLUMNS[i]: (entry[i] if i < len(entry) else None) for i in range(len(SUSPENDED_COLUMNS))}
        doc_file = row.get("suspensionDocumentFile")
        row["suspensionDocumentUrl"] = f"{BASE}/documents/suspended/{doc_file}" if doc_file else None
        rows.append(row)

    return {"rows": rows, "totalAvailable": data.get("recordsTotal"), "totalPages": 1}


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def build_list_record(list_type: str, row: dict, total_available: int | None, total_pages: int | None, page: int) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": f"S1-{list_type}-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": RECORD_TYPES[list_type],
        "_page": page,
        "_totalAvailable": total_available,
        "_totalPages": total_pages,
        **row,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
