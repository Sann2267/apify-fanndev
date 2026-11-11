"""Parsing for the ASP.NET WebForms postback pages served by
`online.gov.sz/e-companysearch.aspx`, plus the raw-passthrough record
builders.

Two page shapes matter here, both plain server-rendered HTML (no JS, no
JSON):

1. The bare search form (`GET`, or a `POST` that hit the timeout/blocked
   path) -- carries the three ASP.NET postback tokens (`__VIEWSTATE`,
   `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`) needed for the next `POST`.
2. The results page (`POST` response) -- either an `id="MainContent_
   GridView1"` `<table>` with one `<tr>` per match, or a
   `id="MainContent_Label2"` "No match was found" marker.
"""

import html
import re
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """The search legitimately matched zero entities (distinct from a
    blocked/error response) -- the page carried the "No match was found for
    the specified company name" label instead of a results table."""


_NO_MATCH_TEXT = "no match was found"

_TOKEN_RE = {
    "__VIEWSTATE": re.compile(r'id="__VIEWSTATE" value="([^"]*)"'),
    "__VIEWSTATEGENERATOR": re.compile(r'id="__VIEWSTATEGENERATOR" value="([^"]*)"'),
    "__EVENTVALIDATION": re.compile(r'id="__EVENTVALIDATION" value="([^"]*)"'),
}


def extract_postback_tokens(page_html: str) -> dict:
    """Pull the three hidden ASP.NET WebForms postback fields out of the
    search-form page. Raises `UnexpectedShape` if any is missing -- the
    postback would silently 500/reject without them, so fail loud here
    instead of downstream."""
    tokens = {}
    for name, pattern in _TOKEN_RE.items():
        m = pattern.search(page_html)
        if not m:
            raise UnexpectedShape(f"{name} not found in search-form page")
        tokens[name] = m.group(1)
    return tokens


_GRID_RE = re.compile(
    r'id="MainContent_GridView1"[^>]*>(.*?)</table>', re.S
)
_LABEL2_RE = re.compile(
    r'id="MainContent_Label2"[^>]*>(.*?)</span>', re.S
)
_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_cell(raw: str) -> str:
    """Strip any nested tags, unescape HTML entities, collapse the padded
    whitespace the GridView renders fixed-width columns with (e.g.
    `"COMPANY REGISTERED                Bad"` -> `"COMPANY REGISTERED"`)."""
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_search_results(page_html: str) -> list[dict]:
    """Parse the `POST` results page into one dict per matched row:
    `{"companyName", "companyStatus", "dateRegistered"}`.

    Raises `NoResultsFound` if the page carries the "No match was found"
    label instead of a results grid. Raises `UnexpectedShape` if the page is
    neither (upstream markup changed).
    """
    grid_match = _GRID_RE.search(page_html)
    if grid_match is None:
        label_match = _LABEL2_RE.search(page_html)
        label_text = _clean_cell(label_match.group(1)).lower() if label_match else ""
        if _NO_MATCH_TEXT in label_text:
            raise NoResultsFound()
        raise UnexpectedShape(
            "Neither #MainContent_GridView1 nor a recognizable "
            f"#MainContent_Label2 no-match marker found (label text: {label_text!r})"
        )

    rows = _ROW_RE.findall(grid_match.group(1))
    results = []
    for row_html in rows[1:]:  # rows[0] is the <th> header row
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 3:
            continue
        results.append(
            {
                "companyName": _clean_cell(cells[0]),
                "companyStatus": _clean_cell(cells[1]),
                "dateRegistered": _clean_cell(cells[2]),
            }
        )
    if not results:
        raise UnexpectedShape("#MainContent_GridView1 present but no data rows parsed out of it")
    return results


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, row: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-aspnet-gridview",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def extract_error(query: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
