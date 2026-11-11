"""HTML parsing for the Solomon Islands Business Registry's "Entity Search"
Catalyst (Foster Moore) service -- see `constants.py` for the full recon
summary of the wire protocol.

Two parsing jobs live here:

1. **Session bootstrap** (`parse_page_state`, `find_button_node`,
   `find_tabs`): every full-page render (search page, entity detail page)
   embeds a fresh `viewInstanceKey` / session-global token / form action, and
   fresh, session-scoped node ids for every clickable control. These are
   ALWAYS parsed from the SAME response they'll be used against -- nothing
   here is a stable constant.

2. **Generic, domain-agnostic field extraction** (`extract_flat_fields`,
   `extract_repeater_groups`): the entity detail page (and each of its tabs)
   is a deeply nested tree of Catalyst's own generic widgets
   (`appAttrLabelBox`/`appAttrValue` label-value pairs, `appRepeater`/
   `appRepeaterNew` record lists). Rather than hand-picking field names
   ("Director", "Shareholder", ...), the tree is walked generically and
   grouped by whatever domain-specific CSS class name Catalyst itself
   generated for that repeater/record (e.g. `...-directorRepeater-director`
   -> `director`) -- this mirrors the raw-passthrough convention already
   used by `botswana-cipa-scraper`'s `walk_record`, adapted for HTML instead
   of a JSON node graph. A record type this actor has never seen before
   (e.g. a register-specific tab on Business Names/Foreign Investments) is
   still captured correctly, under whatever name Catalyst gave it.
"""

import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """The search legitimately matched zero entities: a clean `HTTP 200`
    fragment with zero `a.appItemSearchResult` result links and no error
    marker -- the only reliable zero-match signal found during recon (see
    constants.py)."""


# ---------------------------------------------------------------------------
# Session bootstrap
# ---------------------------------------------------------------------------

_VIKEY_RE = re.compile(r"viewInstanceKey:'([^']+)'")
_SESSGLOBAL_RE = re.compile(r"x-catalyst-session-global':'([^']+)'")
_ACTION_RE = re.compile(r'action="([^"]+update\.html[^"]*)"')


class PageState:
    """The three session-bound values every subsequent POST against this
    view-instance needs. Harvested fresh from a full-page (non-fragment)
    render -- the search start page, or any entity detail page (each has its
    OWN fresh values, not shared with the search page)."""

    def __init__(self, vikey: str, session_global: str, action_url: str):
        self.vikey = vikey
        self.session_global = session_global
        self.action_url = action_url


def parse_page_state(page_html: str) -> PageState:
    vikey_m = _VIKEY_RE.search(page_html)
    sess_m = _SESSGLOBAL_RE.search(page_html)
    action_m = _ACTION_RE.search(page_html)
    if not (vikey_m and sess_m and action_m):
        raise UnexpectedShape("Could not find viewInstanceKey / session-global / form action in page")
    return PageState(vikey_m.group(1), sess_m.group(1), html.unescape(action_m.group(1)))


def find_button_node(page_html: str, label: str) -> tuple[str, str]:
    """Find a button's `catHtmlFragmentCallback` node id + AJAX container id
    by its exact visible label (e.g. "Search"). Searches from the END of the
    page since Catalyst renders "Cancel"/"Reset Search"/"Search" in that
    order and the label must not accidentally match a longer button's tail
    (">Search<" never matches inside ">Reset Search<": the char before
    "Search<" there is a space, not ">")."""
    idx = page_html.rfind(f">{label}<")
    if idx == -1:
        raise UnexpectedShape(f"Button labeled {label!r} not found in page")
    chunk = page_html[max(0, idx - 1000) : idx]
    m = re.search(
        r"catHtmlFragmentCallback\('(\w+)','buttonPush',null,\{asyncUpdate:true,"
        r"containerSelector:'#AsyncWrapper(\w+)'(?:,containerNodeId:'(\w+)')?",
        chunk,
    )
    if not m:
        raise UnexpectedShape(f"No catHtmlFragmentCallback preceding button {label!r}")
    node_id, container_selector_id, container_node_id = m.group(1), m.group(2), m.group(3)
    return node_id, (container_node_id or container_selector_id)


_FORM_INPUT_RE = re.compile(r'<input[^>]*\bname="([^"]+)"[^>]*?(?:\bvalue="([^"]*)")?[^>]*/?>')
_FORM_SELECT_RE = re.compile(r'<select[^>]*\bname="([^"]+)"[^>]*>(.*?)</select>', re.S)
_SELECTED_OPTION_RE = re.compile(r'<option selected="selected" value="([^"]*)"')


def extract_form_fields(form_html: str) -> dict:
    """Current value of every `<input name=...>` / `<select name=...>` in
    the search form, so a POST can carry forward any hidden/advanced-search
    field this actor doesn't explicitly set (mirrors the page's own
    `catCollectFormData`, which submits the WHOLE form's current state, not
    just the fields this actor cares about)."""
    fields = {name: (value or "") for name, value in _FORM_INPUT_RE.findall(form_html)}
    for name, options_html in _FORM_SELECT_RE.findall(form_html):
        m = _SELECTED_OPTION_RE.search(options_html)
        fields[name] = m.group(1) if m else ""
    return fields


_TAB_RE = re.compile(
    r"catHtmlFragmentCallback\('(\w+)','tabSelect',(\d+),\{asyncUpdate:true,"
    r"containerSelector:'#AsyncWrapper(\w+)'(?:,containerNodeId:'(\w+)')?.*?"
    r"<span[^>]*>([^<]+)</span></a></li>",
    re.S,
)


def find_tabs(page_html: str) -> list[dict]:
    """Every detail-page tab (e.g. "General Details", "Addresses",
    "Directors", "Shares & Shareholders", "Filings" -- the exact set varies
    by register/entity, never hardcoded here). Tab 0 ("General Details") is
    always pre-rendered in the page itself; the rest need one fragment POST
    each (`_CBNAME_=tabSelect`, `_CBVALUE_=<index>`) against `nodeId`."""
    tabs = []
    for m in _TAB_RE.finditer(page_html):
        node_id, index, container_selector_id, container_node_id, label = m.groups()
        tabs.append(
            {
                "nodeId": node_id,
                "index": int(index),
                "container": container_node_id or container_selector_id,
                "label": html.unescape(label).strip(),
            }
        )
    return tabs


# ---------------------------------------------------------------------------
# Search-results extraction
# ---------------------------------------------------------------------------

_INVOKE_RE = re.compile(r"catCallback\('(\w+)','invokeMenuCb'")
_LABEL_RE = re.compile(r"^(.*) \(([A-Za-z0-9-]+)\)$")


def extract_search_results(fragment_html: str) -> list[dict]:
    """Parse a search fragment response into one dict per matched entity:
    `{"nodeId", "label", "name", "registrationNumber", "entityTypeBadge",
    **row_fields}`. `nodeId` feeds `open_entity()` in the SAME session.
    Raises `NoResultsFound` if nothing matched (see module docstring)."""
    soup = BeautifulSoup(fragment_html, "lxml")
    links = soup.select("a.appItemSearchResult")
    results = []
    for link in links:
        onclick = link.get("onclick", "")
        m = _INVOKE_RE.search(onclick)
        if not m:
            continue
        node_id = m.group(1)
        label = link.get_text(strip=True)
        lm = _LABEL_RE.match(label)
        name, reg_num = (lm.group(1), lm.group(2)) if lm else (label, None)
        row: dict = {"nodeId": node_id, "label": label, "name": name, "registrationNumber": reg_num}
        row_tag = link.find_parent(class_="appRecordItem")
        if row_tag is not None:
            badge = row_tag.find("abbr")
            if badge is not None:
                row["entityTypeBadge"] = badge.get_text(strip=True) or badge.get("title")
            row.update(extract_flat_fields(row_tag))
            addr = row_tag.select_one(".appSingleLine .appAttrValue")
            if addr is not None:
                row.setdefault("ItemAddress", addr.get_text(" ", strip=True))
            # Search-result rows label their summary attributes (status,
            # incorporation date, sector, ...) with a DIFFERENT widget class
            # than the detail page (`appMinimalAttr`/`appMinimalLabel`/
            # `appMinimalValue`, not `appAttrLabelBox`/`appAttrValue`).
            for attr in row_tag.select(".appMinimalAttr"):
                label_tag = attr.select_one(".appMinimalLabel")
                value_tag = attr.select_one(".appMinimalValue")
                if label_tag is not None and value_tag is not None:
                    label_text = label_tag.get_text(strip=True)
                    if label_text:
                        row[label_text] = value_tag.get_text(" ", strip=True)
        results.append(row)
    if not results:
        raise NoResultsFound()
    return results


# ---------------------------------------------------------------------------
# Generic detail-page field extraction -- domain-agnostic, mirrors upstream's
# own CSS class vocabulary rather than a hand-picked field list.
# ---------------------------------------------------------------------------


def _is_repeater(tag: Tag) -> bool:
    classes = tag.get("class") or []
    return "appRepeater" in classes or "appRepeaterNew" in classes


def _nearest_repeater(tag: Tag, boundary: Tag | None) -> Tag | None:
    """Walk up from `tag` looking for an ancestor repeater wrapper, stopping
    at (not including) `boundary`. Used to tell a flat top-level field apart
    from one that belongs to a nested repeater's row (already handled by the
    recursive call into that row)."""
    for parent in tag.parents:
        if boundary is not None and parent is boundary:
            break
        if _is_repeater(parent):
            return parent
    return None


def _dashed_name(tag: Tag) -> str | None:
    """Catalyst encodes each widget's place in the view definition as a long
    dash-joined CSS class, e.g. `...-directorRepeater-director`. The last
    segment is a stable, upstream-chosen domain name for that widget."""
    candidates = [c for c in (tag.get("class") or []) if c.count("-") >= 2]
    if not candidates:
        return None
    return max(candidates, key=len).rsplit("-", 1)[-1]


def _row_record_name(row: Tag) -> str | None:
    record = row.find(lambda t: t.has_attr("class") and "appRecord" in t.get("class", []))
    return _dashed_name(record) if record is not None else None


_FILING_CLASS_RE = re.compile(r"^appFiling.+")


def extract_flat_fields(container: Tag, boundary: Tag | None = None) -> dict:
    """Flat `{label: value}` pairs directly within `container`, EXCLUDING
    anything that belongs to a nested repeater's row (that's handled by
    `extract_repeater_groups`'s own recursion into each row)."""
    fields: dict = {}
    for label_box in container.select(".appAttrLabelBox"):
        if _nearest_repeater(label_box, boundary) is not None:
            continue
        label_span = label_box.select_one(".appLabelText")
        if label_span is None:
            continue
        label = label_span.get_text(strip=True)
        if not label:
            continue
        parent = label_box.parent
        value_tag = parent.select_one(".appAttrValue") if parent is not None else None
        if value_tag is None:
            continue
        fields[label] = value_tag.get_text(" ", strip=True)
    if not fields:
        # Fallback for widgets that don't use the appAttrLabelBox/appAttrValue
        # pattern at all -- e.g. the Filings tab's bespoke
        # appFilingName/appFilingSubmitted/appFilingEnd markup. Generalized by
        # stripping the shared "appFiling" class prefix rather than
        # hardcoding those three names.
        for el in container.find_all(class_=_FILING_CLASS_RE):
            if _nearest_repeater(el, boundary) is not None:
                continue
            cls = next(c for c in el.get("class", []) if c.startswith("appFiling") and c != "appFiling")
            fields[cls[len("appFiling") :]] = el.get_text(" ", strip=True)
    return fields


def extract_repeater_groups(container: Tag) -> dict:
    """`{domain_name: [record_dict, ...]}` for every top-level repeater found
    within `container` (not nested inside another repeater already being
    walked). Each record dict recursively merges its own flat fields plus
    any further-nested repeater groups (e.g. a contact's phone/email
    sub-repeaters) -- so multiple directors/shareholders/filings naturally
    become a list, with zero hardcoded field/tab names."""
    groups: dict = {}
    for repeater in container.find_all(True):
        if not _is_repeater(repeater):
            continue
        if _nearest_repeater(repeater, container) is not None:
            continue  # nested inside another repeater already covered below
        # NOTE: must use ':scope >' here, not a bare descendant selector --
        # `.select('.appRepeaterContent > .appRepeaterRowContent')` matches
        # ANY matching descendant, including nested sub-repeaters' own rows,
        # silently duplicating their rows into this group.
        rows = repeater.select(":scope > .appRepeaterContent > .appRepeaterRowContent")
        name = _dashed_name(repeater)
        items = []
        for row in rows:
            if name is None:
                name = _row_record_name(row)
            item = extract_flat_fields(row, boundary=row)
            item.update(extract_repeater_groups(row))
            items.append(item)
        if items:
            groups.setdefault(name or "items", []).extend(items)
    return groups


def extract_detail_tab(fragment_or_page_html: str, scope_selector: str | None = None) -> dict:
    """Full extraction (flat fields + repeater groups) for one detail-page
    tab's HTML (either the pre-rendered tab-0 section of a full page, scoped
    via `scope_selector`, or a `tabSelect` fragment response as-is)."""
    soup = BeautifulSoup(fragment_or_page_html, "lxml")
    scope = soup.select_one(scope_selector) if scope_selector else (soup.body or soup)
    if scope is None:
        raise UnexpectedShape(f"Scope {scope_selector!r} not found in tab HTML")
    result = extract_flat_fields(scope)
    result.update(extract_repeater_groups(scope))
    return result


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_detail_record(query: str, entity_view_url: str, detail: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-catalyst-entityview",
        "_scrapedAt": utc_now_iso(),
        "entityViewUrl": entity_view_url,
        **detail,
    }


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
