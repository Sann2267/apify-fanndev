"""Parsing helpers for the COJ `CompanySearch.aspx` flow, plus the
raw-passthrough record builders.

Two shapes need parsing:

1. The ASP.NET WebForms postback fields (`__VIEWSTATE`,
   `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`) and the async-job hidden
   fields (`ctl00_Space_Response`, `ctl00_Space_PollURL`,
   `ctl00_Space_ResultUiController`) -- plain `<input type="hidden"
   name="..." value="...">` tags, pulled with a small regex helper.
2. The final results page's inline `var database = {...};` blob -- a
   balanced-brace walk (not a naive non-greedy regex) because the address/
   name fields inside it can legitimately contain `}`-adjacent punctuation
   and the object is deeply nested, per `.ai/skills/balanced-brace-json`.
"""

import json
import re
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """The search legitimately matched zero entities (the results blob's
    `data` array is empty)."""


# ---------------------------------------------------------------------------
# Hidden-field extraction (ASP.NET postback fields + async-job fields)
# ---------------------------------------------------------------------------

def extract_hidden_field(name: str, html: str) -> str | None:
    """Pull the `value="..."` of a `<input type="hidden" name="<name>" ...>`
    (or `id="<name>"`) tag. Attribute order on this site varies (`name`
    before `value` vs `id` before `value`), so both are tried."""
    for pattern in (
        rf'name="{re.escape(name)}"[^>]*value="([^"]*)"',
        rf'id="{re.escape(name)}"[^>]*value="([^"]*)"',
    ):
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None


def extract_redirect_target(js_snippet: str) -> str | None:
    """The tiny post-POST/post-GET response body is a `<script>` that ends
    with `window.location='<url>'` (single-quoted, JS-escaped `\\/`)."""
    m = re.search(r"window\.location\s*=\s*'([^']+)'", js_snippet)
    if not m:
        return None
    return m.group(1).replace("\\/", "/")


# ---------------------------------------------------------------------------
# Balanced-brace extraction of `var database = {...};`
# ---------------------------------------------------------------------------

def _extract_balanced_braces(text: str, start: int) -> str | None:
    """Given text and the index of the opening '{', return the substring
    through the matching '}'. Handles escaped chars inside strings and
    nested objects/arrays correctly. See `.ai/skills/balanced-brace-json`."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def extract_database_blob(html: str) -> dict:
    """Extract and JSON-parse the `var database = {...};` blob embedded in
    `CompanySearchResults.aspx`. Raises `UnexpectedShape` if the anchor or a
    balanced object isn't found, or if it doesn't parse as JSON."""
    anchor = "var database = "
    pos = html.find(anchor)
    if pos == -1:
        raise UnexpectedShape("'var database = ' anchor not found in results page")
    brace_start = pos + len(anchor)
    if brace_start >= len(html) or html[brace_start] != "{":
        raise UnexpectedShape("no '{' immediately after 'var database = ' anchor")
    blob = _extract_balanced_braces(html, brace_start)
    if blob is None:
        raise UnexpectedShape("unbalanced braces in 'var database = {...}' blob")
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"database blob did not parse as JSON: {e}") from e


def extract_search_rows(database: dict) -> list[dict]:
    """Return the `data` array of matched-entity rows. Raises
    `NoResultsFound` if it's a (well-formed, empty) list -- the documented
    zero-match shape. Raises `UnexpectedShape` if `data` is missing or not a
    list at all (a real shape change, not a zero-match)."""
    if "data" not in database:
        raise UnexpectedShape(f"database blob has no 'data' key; keys={sorted(database)}")
    rows = database["data"]
    if not isinstance(rows, list):
        raise UnexpectedShape(f"database['data'] is {type(rows).__name__}, expected list")
    if not rows:
        raise NoResultsFound()
    return rows


# ---------------------------------------------------------------------------
# Record builders (raw passthrough + envelope)
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(query: str, row: dict) -> dict:
    """Raw passthrough of upstream's own row shape (link/rank/id/name/
    office/status/type/date/address/number/documentCount), verbatim field
    names, plus the standard envelope."""
    return {
        "_input": query,
        "_source": "S1-companysearch",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error(query: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
