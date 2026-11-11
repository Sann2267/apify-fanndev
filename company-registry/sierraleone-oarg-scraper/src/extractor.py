"""Parsing logic -- turns the OARG Company Search HTML page into records.

See client.py / constants.py for how the page is obtained. Four shapes
observed (see CRAWLING_METHOD.md for the raw HTML of each):

  1. Match(es) found -- a `div.alert-danger` reading
     "<query> already exist." followed by one `<tr><td>NAME</td></tr>` per
     existing matching business name (name only, no other fields).
  2. No matches -- a `div.alert-success` reading "<query> is available."
     and no result rows.
  3. Query too short -- plain text "Minimum length is 3" (no alert div,
     no table rows); the site enforces a 3-character minimum.
  4. Backend crash -- an apostrophe or semicolon in the query makes the
     PHP backend die mid-render (suppressed fatal error): the response is
     truncated right after the search form, missing the alert div, the
     results table, the footer, and the closing </html> tag entirely.
"""

import html
import re
from datetime import datetime, timezone

SOURCE = "S1-company-search"

_STATUS_RE = re.compile(r"<strong>(.*?)</strong>\s*(already exist|is available)", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr>\s*<td>(.*?)</td>\s*</tr>", re.IGNORECASE | re.DOTALL)
_TOO_SHORT_RE = re.compile(r"Minimum length is\s*(\d+)", re.IGNORECASE)


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_search_page(html_text: str) -> dict:
    """Returns one of:
    {"kind": "results", "matches": [str, ...]}
    {"kind": "available"}
    {"kind": "validation_error", "detail": str}
    {"kind": "server_error", "detail": str}
    Raises UnexpectedShape if none of the four known shapes match.
    """
    if "</html>" not in html_text or "az-footer" not in html_text:
        return {
            "kind": "server_error",
            "detail": (
                "Upstream response was truncated mid-render (no closing </html> / footer found). "
                "Known cause: an apostrophe (') or semicolon (;) in the query crashes OARG's backend. "
                "This is an upstream bug, not a transient failure -- retrying will not help."
            ),
        }

    status_match = _STATUS_RE.search(html_text)
    if status_match is not None:
        status = status_match.group(2).lower()
        if status == "already exist":
            matches = [html.unescape(m).strip() for m in _ROW_RE.findall(html_text)]
            matches = [m for m in matches if m]
            if not matches:
                raise UnexpectedShape(
                    "Page said the name 'already exist' but no <tr><td> result rows were found -- "
                    "page shape has likely changed."
                )
            return {"kind": "results", "matches": matches}
        # "is available"
        return {"kind": "available"}

    too_short = _TOO_SHORT_RE.search(html_text)
    if too_short is not None:
        return {"kind": "validation_error", "detail": too_short.group(0)}

    raise UnexpectedShape(
        "Page has none of: an already-exist/is-available alert banner, a 'Minimum length' notice, "
        "or a truncated/crashed response -- page shape has likely changed."
    )


def build_match_record(query: str, matched_name: str, total_matches: int, truncated: bool) -> dict:
    return {
        "_input": query,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "nameExists": True,
        "_totalMatches": total_matches,
        "_truncated": truncated,
        "matchedBusinessName": matched_name,
    }


def build_available_record(query: str) -> dict:
    return {
        "_input": query,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "nameExists": False,
        "_totalMatches": 0,
        "_truncated": False,
    }


def build_error_record(query: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
