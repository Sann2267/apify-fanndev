"""Parsing + raw-passthrough record builders for UMUCYO (Rwanda e-GP).

Two shapes feed this actor, both server-rendered JSP HTML (no JSON API
exists -- see `constants.py`):

1. **Listing rows** -- the "List of advertising (all)" table, one row per
   tender notice, with a pipe-delimited hidden `<input>` value carrying the
   internal reference codes needed to fetch that tender's detail page.
2. **Detail pages** -- a label/value `<th>`/`<td>` table whose exact label
   set varies by tender type (Goods/Works/Services/Consultant) and stage,
   so it is parsed generically (every `<th>` label mapped to its sibling
   `<td>`) rather than against a fixed field list, plus a separate
   attachments table and a raw-text fallback so nothing on the page is
   silently dropped even if a future template variant isn't covered by the
   generic label scan.

Both are normalized into the same dataset envelope (`_mode`/`_source`/
`_scrapedAt`) with upstream's own field names/labels passed through
unchanged.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESULTS_COUNT_RE = re.compile(
    r'<span class="point">([\d,]+)</span>\s*Results\s*\(page\s*<span class="point">(\d+)</span>/(\d+)\)',
    re.S,
)
ATTACHMENT_RE = re.compile(
    r"util_fileIdDownload\('([^']+)'\)[^>]*>\s*</a>|util_fileIdDownload\('([^']+)'\).*?>\s*([^<]+?)\s*</a>",
    re.S,
)
# Labels belonging to the attachments table -- excluded from the generic
# th/td label scan since they're captured separately by _parse_attachments.
_ATTACHMENT_TABLE_LABELS = {"No", "Document Name", "Upload Date", "File"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_label(th) -> str:
    return th.get_text(" ", strip=True).replace("*", "").strip(" :")


# ---------------------------------------------------------------------------
# Listing (HTML table scrape)
# ---------------------------------------------------------------------------


def parse_list_page(html: str) -> tuple[list[dict], int, int, int]:
    """Returns (items, total_results, current_page, total_pages)."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="contents_R")
    if container is None:
        raise RuntimeError("`#contents_R` not found on listing page -- page shape may have changed")

    m = RESULTS_COUNT_RE.search(html)
    if not m:
        raise RuntimeError("Results-count footer not found -- page shape may have changed")
    total_results = int(m.group(1).replace(",", ""))
    current_page = int(m.group(2))
    total_pages = int(m.group(3))

    items = []
    for row in container.select("table.article_table tbody tr"):
        radio = row.find("input", attrs={"name": "tenderNo"})
        cells = row.find_all("td", recursive=False)
        if radio is None or len(cells) < 8:
            continue
        parts = (radio.get("value") or "").split("|")
        if len(parts) < 7:
            continue
        tend_refer_no = parts[0]
        tend_stage_cd = parts[-5]
        tend_mthod_cd = parts[-4]
        tend_type_cd = parts[-3]
        status_cd = parts[-1]

        title_link = cells[1].find("a")
        title = title_link.get_text(strip=True) if title_link else cells[1].get_text(strip=True)
        tender_no_text = next(cells[2].stripped_strings, None)

        items.append(
            {
                "tender_name": title,
                "tender_no": tender_no_text,
                "tend_refer_no": tend_refer_no,
                "tend_stage_cd": tend_stage_cd,
                "tend_mthod_cd": tend_mthod_cd,
                "tend_type_cd": tend_type_cd,
                "status_cd": status_cd,
                "status": cells[3].get_text(strip=True),
                "advertising_date": cells[4].get_text(strip=True),
                "deadline_of_submitting": cells[5].get_text(strip=True),
                "planned_open_date": cells[6].get_text(strip=True),
                "stage_type": cells[7].get_text(strip=True),
                "detail_ref": f"{tend_refer_no}|{tend_stage_cd}|{tend_type_cd}",
            }
        )
    return items, total_results, current_page, total_pages


# ---------------------------------------------------------------------------
# Detail page (generic label/value scan + attachments + raw-text fallback)
# ---------------------------------------------------------------------------


def _parse_attachments(container) -> list[dict]:
    attachments = []
    for a in container.find_all("a", onclick=re.compile("util_fileIdDownload")):
        m = re.search(r"util_fileIdDownload\('([^']+)'\)", a.get("onclick") or "")
        if not m:
            continue
        row = a.find_parent("tr")
        doc_name = None
        upload_date = None
        if row is not None:
            tds = row.find_all("td", recursive=False)
            if len(tds) >= 3:
                doc_name = tds[1].get_text(strip=True)
                upload_date = tds[2].get_text(strip=True)
        attachments.append(
            {
                "file_id": m.group(1),
                "file_name": a.get_text(strip=True) or None,
                "document_name": doc_name,
                "upload_date": upload_date,
            }
        )
    return attachments


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="contents_R")
    if container is None:
        raise RuntimeError("`#contents_R` not found on detail page -- page shape may have changed")

    heading = container.find("h3", class_="clearfix")
    detail_page_heading = heading.get_text(strip=True) if heading else None

    fields: dict[str, str] = {}
    for th in container.find_all("th"):
        label = _clean_label(th)
        if not label or label in _ATTACHMENT_TABLE_LABELS:
            continue
        td = th.find_next_sibling("td")
        if td is None:
            continue
        value = td.get_text(" ", strip=True)
        if value:
            # A handful of label variants repeat innocuously (e.g. "Lot X"
            # rows); keep the first occurrence, never overwrite silently.
            fields.setdefault(label, value)

    attachments = _parse_attachments(container)

    # Raw-text fallback -- older/alternate templates (e.g. "Request for
    # Expressions of Interest") embed key info as inline paragraph text
    # ("TITLE: ... CLIENT: ... SOURCE OF FUNDS: ...") rather than in the
    # th/td table. Captured unconditionally so nothing is silently lost.
    for tag in container.find_all(["script", "style"]):
        tag.decompose()
    raw_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True)).strip()

    return {
        "detail_page_heading": detail_page_heading,
        "fields": fields,
        "attachments": attachments,
        "raw_text": raw_text,
    }


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
