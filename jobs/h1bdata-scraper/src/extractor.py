"""Parsing logic -- turns h1bdata.info's plain HTML tables into
dataset-ready records.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no semantic renaming) -- both h1bdata.info tables are themselves
just label/value HTML (no JSON API, no JSON-LD), so "verbatim" here means
the site's own column headers / detail-page labels, normalized only for
use as dict keys (uppercase, spaces/punctuation -> underscore -- e.g. the
detail page's "LCA CASE EMPLOYER NAME" label becomes the key
"LCA_CASE_EMPLOYER_NAME"). No column is dropped, reordered, or given a
different name than what h1bdata.info itself displays.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

CASE_ID_RE = re.compile(r"details\.php\?id=([^&\"']+)")
LABEL_KEY_RE = re.compile(r"[^A-Z0-9]+")


class UnexpectedShape(Exception):
    """Upstream HTML shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label_to_key(label: str) -> str:
    key = LABEL_KEY_RE.sub("_", label.strip().upper()).strip("_")
    return key or "UNKNOWN"


def extract_search_page(html: str) -> list[dict]:
    """Returns raw row dicts from the `#myTable` search-results table.

    Empty list means the query legitimately matched nothing (h1bdata.info
    renders an empty `<tbody></tbody>` for a no-match search -- confirmed
    live, see CRAWLING_METHOD.md). A missing table entirely is treated as
    a shape change, not a no-match.
    """
    tree = HTMLParser(html)
    table = tree.css_first("table#myTable")
    if table is None:
        raise UnexpectedShape("table#myTable not found on search results page -- shape has likely changed.")

    rows = []
    for tr in table.css("tbody > tr"):
        cells = tr.css("td")
        if len(cells) < 6:
            continue  # defensive -- skip any stray malformed row rather than crash the whole page
        employer = cells[0].text(strip=True)
        job_title = cells[1].text(strip=True)
        base_salary = cells[2].text(strip=True)
        location = cells[3].text(strip=True)
        submit_date = cells[4].text(strip=True)
        start_date = cells[5].text(strip=True)

        case_id = None
        salary_link = cells[2].css_first("a")
        if salary_link is not None:
            m = CASE_ID_RE.search(salary_link.attributes.get("href") or "")
            if m:
                case_id = m.group(1)

        rows.append({
            "EMPLOYER": employer,
            "JOB_TITLE": job_title,
            "BASE_SALARY": base_salary,
            "LOCATION": location,
            "SUBMIT_DATE": submit_date,
            "START_DATE": start_date,
            # Derived, not an upstream column -- kept as plain (non-upper)
            # keys per convention ("genuinely new data this actor adds").
            "caseId": case_id,
            "caseUrl": f"https://h1bdata.info/details.php?id={case_id}" if case_id else None,
        })
    return rows


def extract_case_detail(html: str) -> dict | None:
    """Returns the full LCA case record from a `details.php?id=...` page
    as a flat dict keyed by h1bdata.info's own field labels. Returns None
    if the page 200'd but carries no record table (confirmed live for an
    invalid/unknown case id -- see CRAWLING_METHOD.md)."""
    tree = HTMLParser(html)
    table = tree.css_first("table.table-striped")
    if table is None:
        return None

    record: dict = {}
    for tr in table.css("tbody > tr"):
        cells = tr.css("td")
        if len(cells) != 2:
            continue
        label = cells[0].text(strip=True)
        value = cells[1].text(strip=True)
        if not label:
            continue
        record[_label_to_key(label)] = value

    if not record:
        return None
    return record


def wrap(item: dict, input_value: str, source: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
