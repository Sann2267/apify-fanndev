"""Parsing for Samoa's "Business Registries" (Catalyst-framework) HTML.

Unlike Botswana CIPA's Verne app (`botswana-cipa-scraper`), this site never
hands back clean JSON -- everything is server-rendered HTML, both the search
results and the company-detail tabs. Two shapes matter:

1. **Fragment responses** (`POST .../viewInstance/update.html?id=...` with
   `_CBHTMLFRAG_=true`) -- the requested HTML is wrapped in a pair of HTML
   comments, `<!--FB<id>--><!--FE<id>-->`, where `<id>` is the arbitrary
   `_CBHTMLFRAGID_` value the caller sent. `unwrap_fragment` extracts the
   middle, mirroring the site's own client-side `catUnwrapFragment`.
2. **Repeated records** (search-result rows, directors, shareholders, share
   parcels, filings) -- each is one `<div class="appRepeaterRowContent ...">`
   sibling inside an `appRepeaterContent` container. `split_rows` splits on
   that literal marker (safe here: no nested `appRepeaterRowContent` blocks
   were observed inside a row during recon).

Field values are extracted generically via `LABEL_VALUE_RE`, which pairs
every `appLabelText">LABEL` with the immediately-following
`class="appAttrValue">VALUE</div>` (used for both the free-standing
General-Details-style fields AND directors/shareholders/addresses rows --
same underlying widget). This is deliberately NOT a hardcoded field list:
MCIL's own label text becomes the dict key verbatim, so a label this actor
hasn't seen before still comes through instead of being silently dropped.

A recurring quirk: many date/text values are rendered as TWO adjacent spans
carrying the same text twice (`<span aria-hidden="true">X</span><span
class="appOffScreenText">X</span>` -- a sighted-vs-screen-reader duplicate),
which naively stripping tags turns into "XX" (e.g. "18-Jul-197718-Jul-1977").
`clean_value` special-cases this by keeping only the first inner span's text
when that pattern is present.
"""

import html as _html
import re
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """The search legitimately matched zero companies -- the response's own
    `id="appSearchNoResults"` marker ("No search results found") was
    present. This is a clean, unambiguous signal (unlike Botswana CIPA's
    Verne app, where the analogous marker is present even alongside real
    results) -- see CRAWLING_METHOD.md."""


# ---------------------------------------------------------------------------
# Wire-format helpers
# ---------------------------------------------------------------------------


def unwrap_fragment(response_html: str, frag_id: str) -> str:
    """Extract the content between `<!--FB<frag_id>-->` and
    `<!--FE<frag_id>-->` from a fragment-mode POST response."""
    m = re.search(
        re.escape(f"<!--FB{frag_id}-->") + r"(.*)" + re.escape(f"<!--FE{frag_id}-->"),
        response_html,
        re.S,
    )
    if not m:
        raise UnexpectedShape(f"fragment markers FB{frag_id}/FE{frag_id} not found in response")
    return m.group(1)


def split_rows(container_html: str) -> list[str]:
    """Split a repeater's content into one HTML chunk per
    `appRepeaterRowContent` row (the first chunk, before any row, is
    discarded). Split on the bare class name, not `class="appRepeaterRow...`
    -- search-result rows render it as the FIRST class token
    (`class="appRepeaterRowContent appRowOdd ...`) but detail-tab rows
    (addresses/directors/shareholders/share parcels) render it after
    `appReadOnly ` instead (`class="appReadOnly appRepeaterRowContent ...`),
    so anchoring to `class="` specifically missed every one of those."""
    parts = container_html.split("appRepeaterRowContent")
    return parts[1:]


_TAG_RE = re.compile(r"<[^>]+>")


def clean_value(raw: str) -> str:
    """Strip tags/entities from a captured value, collapsing the visible/
    screen-reader duplicate pattern (e.g. `04-Mar-2003<span class=
    "appOffScreenText">04-Mar-2003</span>` -> "04-Mar-200304-Mar-2003" once
    tags are stripped) down to a single copy. The duplicate's exact markup
    varies (sometimes a plain-text-then-span pair, sometimes two spans), so
    this collapses on the FINAL flattened text (`text == first_half +
    first_half`) rather than trying to match every markup variant."""
    text = _html.unescape(_TAG_RE.sub("", raw)).strip()
    n = len(text)
    if n > 1 and n % 2 == 0:
        half = n // 2
        if text[:half] == text[half:]:
            return text[:half]
    return text


_LABEL_VALUE_RE = re.compile(r'appLabelText">([^<]*)<.*?appAttrValue"[^>]*>(.*?)</div>', re.S)


def parse_label_value_pairs(block_html: str) -> dict:
    """Generic `{label: value}` extraction for one record's HTML (a search
    result row, a director/shareholder/address row, or the whole
    General-Details tab). Blank labels (used by nested sub-repeaters like
    "Previously Known As") are skipped here -- callers that need those
    extract them separately before calling this."""
    out: dict = {}
    for label, raw_value in _LABEL_VALUE_RE.findall(block_html):
        label = label.strip()
        if not label:
            continue
        out[label] = clean_value(raw_value)
    return out


_MINIMAL_LABEL_VALUE_RE = re.compile(
    r'appMinimalLabel">([^<]*)</span>\s*<span class="appMinimalValue"[^>]*>([^<]*)</span>'
)


def parse_minimal_pairs(block_html: str) -> dict:
    """Same idea as `parse_label_value_pairs` but for the "minimal display"
    widget used on search-result rows (`appMinimalLabel`/`appMinimalValue`
    span pairs instead of `appAttrLabelBox`/`appAttrValue` divs)."""
    out: dict = {}
    for label, value in _MINIMAL_LABEL_VALUE_RE.findall(block_html):
        label = label.strip()
        if not label:
            continue
        out[label] = _html.unescape(value.strip())
    return out


# ---------------------------------------------------------------------------
# Search results
# ---------------------------------------------------------------------------

_CLICK_ID_RE = re.compile(r"catCallback\('(W\d+)','invokeMenuCb'")
# Greedy (not `[^<(]*`) because the company name itself can legitimately
# contain parentheses (e.g. "DIGICEL (SAMOA) FINANCIAL SERVICES LIMITED
# (0460)") -- greedy backtracking correctly lands on the LAST "(<digits>)"
# immediately before the closing tag.
_NAME_NUM_RE = re.compile(r"<span>(.*)\s\((\d+)\)</span>")
_BADGE_RE = re.compile(r'abbr title="([^"]*)" class="appBadge[^"]*">([^<]*)')
_ADDRESS_RE = re.compile(r'itemAddress[^>]*>.*?appAttrValue">([^<]*)</div>', re.S)
_PREV_NAMES_BLOCK_RE = re.compile(r'class="appMinimalRep previousNamesRepeater">(.*?)</div>\s*</div>', re.S)
_PREV_NAME_VALUE_RE = re.compile(r'appMinimalValue">([^<]*)</span>')
_SELECT_PAGE_NODE_RE = re.compile(r"catHtmlFragmentCallback\('(W\d+)','selectPage'")


def extract_search_results(fragment_html: str) -> list[dict]:
    """Parse one page of search-results rows out of a search (or
    `selectPage`) fragment response. Raises `NoResultsFound` if the page's
    own "No search results found" marker is present with zero rows; raises
    `UnexpectedShape` if neither rows nor that marker are found (shape
    changed upstream)."""
    rows_html = split_rows(fragment_html)
    if not rows_html:
        if 'id="appSearchNoResults"' in fragment_html:
            raise NoResultsFound()
        raise UnexpectedShape("no result rows and no 'No search results found' marker in response")

    results = []
    for row_html in rows_html:
        click_m = _CLICK_ID_RE.search(row_html)
        name_m = _NAME_NUM_RE.search(row_html)
        if not click_m or not name_m:
            continue  # not an entity row (shouldn't happen, but fail soft here -- caller sees fewer rows, not a crash)
        badge_m = _BADGE_RE.search(row_html)
        addr_m = _ADDRESS_RE.search(row_html)
        prev_m = _PREV_NAMES_BLOCK_RE.search(row_html)
        previous_names = _PREV_NAME_VALUE_RE.findall(prev_m.group(1)) if prev_m else []
        row = {
            "nodeId": click_m.group(1),
            "name": _html.unescape(name_m.group(1).strip()),
            "registrationNumber": name_m.group(2),
            "entityTypeAbbrev": badge_m.group(2) if badge_m else None,
            "entityTypeLabel": badge_m.group(1) if badge_m else None,
            "address": clean_value(addr_m.group(1)) if addr_m else None,
            "previousNames": [_html.unescape(n.strip()) for n in previous_names],
            **parse_minimal_pairs(row_html),
        }
        results.append(row)
    return results


def find_pager_node_id(fragment_html: str) -> str | None:
    m = _SELECT_PAGE_NODE_RE.search(fragment_html)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Company detail
# ---------------------------------------------------------------------------

_FILING_RE = re.compile(
    r'appFilingOpen"[^>]*><span>([^<]*)</span></a></div>\s*'
    r'<div class="appFilingSubmitted"[^>]*><span[^>]*>([^<]*)</span>.*?'
    r'<div class="appFilingEnd"[^>]*><span[^>]*>([^<]*)</span>',
    re.S,
)


def extract_general_details(detail_html: str) -> dict:
    """The "General Details" tab (index 0) is embedded directly in the
    initial detail-page HTML -- no extra POST needed. Uses the same
    label/value widget as the other tabs."""
    return parse_label_value_pairs(detail_html)


def extract_tab_records(tab_html: str) -> list[dict]:
    """Addresses / Directors / Shareholders / Share Parcels tabs all use the
    same repeated-row shape -- one dict of label/value pairs per row."""
    return [parse_label_value_pairs(row) for row in split_rows(tab_html) if parse_label_value_pairs(row)]


def extract_filings(tab_html: str) -> list[dict]:
    """The Filings tab uses its own simpler `appFiling*` markup (no
    label/value widget) -- filing type (form name), submission timestamp,
    and filed/completed timestamp. Filing document DOWNLOAD (the
    `openFiling` click target) was not pursued -- see CRAWLING_METHOD.md."""
    return [
        {"filingType": ftype.strip(), "submittedAt": submitted.strip(), "filedAt": filed.strip()}
        for ftype, submitted, filed in _FILING_RE.findall(tab_html)
    ]


# ---------------------------------------------------------------------------
# Record builders (raw-passthrough convention)
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_detail_record(query: str, row: dict, detail: dict) -> dict:
    record = {
        "_input": query,
        "_source": "S1-catalyst-detail",
        "_scrapedAt": utc_now_iso(),
        "name": row.get("name"),
        "registrationNumber": row.get("registrationNumber"),
        "entityTypeLabel": row.get("entityTypeLabel"),
    }
    record.update(detail)
    return record


def build_summary_record(query: str, row: dict) -> dict:
    row = dict(row)
    row.pop("nodeId", None)  # session-scoped, meaningless outside this run
    return {
        "_input": query,
        "_source": "S1-catalyst-searchresult",
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
