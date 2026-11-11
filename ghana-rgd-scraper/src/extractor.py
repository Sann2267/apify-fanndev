"""Parsing logic -- turns the ORC Name Search htmx fragment into records.

See client.py / constants.py for how the fragment is obtained. Three shapes
observed (see CRAWLING_METHOD.md for the raw HTML of each):

  1. Results table -- `table#search-results-tbl`, caption text
     "Retrieved N business name(s)", rows as
     `<tr data-bizcode="XX" data-bizname="...">` with a second `<td><span>`
     carrying the human-readable entity-type label.
  2. Empty results -- a `#no-search-results` div, "No data found".
  3. Server-side validation error -- a `div.error-message` with zero or one
     child `<div>` carrying message text (a blank `bizName` gives
     "Please enter name to search for"; an overly-short "starts with" query
     gives an empty message with the same wrapper markup).
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SOURCE = "S1-name-search"


class UnexpectedShape(Exception):
    """Upstream fragment shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_search_fragment(html_text: str) -> dict:
    """Returns one of:
    {"kind": "results", "totalAvailable": int, "matches": [{"businessName", "businessType", "businessTypeCode"}, ...]}
    {"kind": "empty"}
    {"kind": "validation_error", "detail": str}
    Raises UnexpectedShape if none of the three known shapes match.
    """
    soup = BeautifulSoup(html_text, "lxml")

    error_div = soup.select_one("div.error-message")
    if error_div is not None:
        detail = error_div.get_text(" ", strip=True)
        return {"kind": "validation_error", "detail": detail}

    if soup.select_one("#no-search-results") is not None:
        return {"kind": "empty"}

    table = soup.select_one("table#search-results-tbl")
    if table is None:
        raise UnexpectedShape(
            "Fragment has none of: div.error-message, #no-search-results, table#search-results-tbl -- "
            "page shape has likely changed."
        )

    caption_text = table.get_text(" ", strip=True)
    count_match = re.search(r"Retrieved\s+(\d+)\s+business name", caption_text)
    total_available = int(count_match.group(1)) if count_match else None

    matches = []
    for row in table.select("tbody tr[data-bizcode]"):
        biz_code = row.get("data-bizcode")
        biz_name = (row.get("data-bizname") or "").strip()
        cells = row.select("td")
        type_label = cells[1].get_text(strip=True) if len(cells) >= 2 else None
        if not biz_name:
            continue
        matches.append(
            {
                "businessName": biz_name,
                "businessType": type_label,
                "businessTypeCode": biz_code,
            }
        )

    if total_available is None:
        total_available = len(matches)

    return {"kind": "results", "totalAvailable": total_available, "matches": matches}


def build_match_record(query: str, search_type: str, match: dict, total_available: int, truncated: bool) -> dict:
    return {
        "_input": query,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "searchType": search_type,
        "_totalAvailable": total_available,
        "_truncated": truncated,
        "businessName": match["businessName"],
        "businessType": match["businessType"],
        "businessTypeCode": match["businessTypeCode"],
    }


def build_empty_record(query: str, search_type: str) -> dict:
    return {
        "_input": query,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "searchType": search_type,
        "_totalAvailable": 0,
        "_truncated": False,
        "_error": "no_results",
    }


def build_error_record(query: str, search_type: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "searchType": search_type,
        "_error": error_kind,
        "_errorDetail": detail,
    }
