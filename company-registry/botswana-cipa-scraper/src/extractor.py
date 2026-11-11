"""Parsing for the Verne (Foster Moore) view-tree format used by CIPA's
"Search the Register" service, plus the raw-passthrough record builders.

Two wire shapes carry the SAME logical structure (a flat map of
`node_id -> node`, each node optionally carrying `children: [node_id, ...]`,
`nodetype`, `domain`, `attribute`/`attributeValue`, `text`, `widget`, `kv`):

1. **SSR page embed** (`GET` responses) -- a real, clean JS object literal
   (`var viewTree = {...};`) in the HTML. Parsed with `json.loads` via
   `parse_view_tree_from_html`.
2. **AJAX delta responses** (`POST /master/ui/<txn>`) -- a compact,
   XML-*looking* but NOT well-formed-XML serialization (tag names are the
   hex node IDs themselves, which XML forbids starting with a digit). Parsed
   by hand with regex in `parse_delta_state`.

Both are normalized into the same `{node_id: {...}}` shape so `walk_record`
(a single generic, domain-agnostic tree flattener) works on either. This is
deliberate: CIPA exposes no traditional JSON REST API, so this node-graph
*is* upstream's own data model -- `walk_record` mirrors the raw-passthrough
convention (see `.ai/conventions/dataset-envelope.md`) by grouping on
upstream's own `domain`/`attribute` vocabulary instead of hand-picking
fields, so it doesn't silently drop a role type (e.g. a corporate
shareholder shaped differently from an individual one) it hasn't been told
about explicitly.
"""

import html
import json
import re
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream view-tree shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


class NoResultsFound(Exception):
    """The search legitimately matched zero entities (distinct from a
    blocked/error response) -- no `Name (REGNUM)`-labeled hyperlink button
    was found in the response. See `extract_search_results` for why this is
    the only reliable zero-match signal found during recon."""


# ---------------------------------------------------------------------------
# Wire-format parsing
# ---------------------------------------------------------------------------

_VIEWTREE_RE = re.compile(r"var viewTree = (\{.*?\});\s*\n\s*for \(key in viewTree\)", re.S)


def parse_view_tree_from_html(page_html: str) -> dict:
    """Extract and JSON-parse the SSR-embedded `var viewTree = {...}` object
    from a Verne page (search start page or entityView detail page)."""
    m = _VIEWTREE_RE.search(page_html)
    if not m:
        raise UnexpectedShape("var viewTree = {...} not found in page HTML")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"viewTree JSON did not parse: {e}") from e


_NODE_RE = re.compile(r"<([0-9a-f]{16})>(.*?)</\1>", re.S)
_SCALAR_TAGS = ("nodetype", "domain", "attribute", "attributeValue", "widget")
_FIELD_RE = re.compile(r"<([a-zA-Z][\w-]*)>(.*?)</\1>", re.S)
_CHILDREN_RE = re.compile(r"<children>([0-9a-f]{16})</children>")


def parse_delta_state(text: str) -> dict:
    """Parse a `POST /master/ui/<txn>` response body's `<state>...</state>`
    block into the same `{node_id: {...}}` shape as `parse_view_tree_from_html`.

    Not real XML (node-id tag names can start with a digit, which XML
    forbids) -- hand-rolled with regex instead of an XML parser. Each node's
    own wrapping tag is unique in the tree (IDs aren't reused), so a
    non-greedy `.*?` up to the matching closing tag is safe.
    """
    m = re.search(r"<state>(.*)</state>", text, re.S)
    if not m:
        raise UnexpectedShape("<state>...</state> not found in AJAX response")
    body = m.group(1)
    nodes: dict = {}
    for node_id, inner in _NODE_RE.findall(body):
        node: dict = {}
        children = _CHILDREN_RE.findall(inner)
        if children:
            node["children"] = children
        for tag in _SCALAR_TAGS:
            tm = re.search(rf"<{tag}>(.*?)</{tag}>", inner, re.S)
            if tm:
                node[tag] = html.unescape(tm.group(1))
        tm = re.search(r"<text>(.*?)</text>", inner, re.S)
        if tm:
            node["text"] = {k: html.unescape(v) for k, v in _FIELD_RE.findall(tm.group(1))}
        km = re.search(r"<kv>(.*?)</kv>", inner, re.S)
        if km:
            node["kv"] = {k: html.unescape(v) for k, v in _FIELD_RE.findall(km.group(1))}
        nodes[node_id] = node
    return nodes


def find_by_attribute(node_map: dict, attribute: str) -> str | None:
    """Return the node id of the (first) attribute node with this `attribute`
    name, e.g. `NameOrNumber`."""
    for node_id, node in node_map.items():
        if isinstance(node, dict) and node.get("attribute") == attribute:
            return node_id
    return None


def find_button_by_label(node_map: dict, label: str) -> str | None:
    for node_id, node in node_map.items():
        if not isinstance(node, dict) or node.get("nodetype") != "button":
            continue
        text = node.get("text")
        if isinstance(text, dict) and text.get("label") == label:
            return node_id
    return None


# ---------------------------------------------------------------------------
# Generic tree walker -- domain-agnostic, mirrors upstream's own vocabulary
# ---------------------------------------------------------------------------

def walk_record(node_id: str, node_map: dict, visited: set | None = None) -> tuple[dict, dict]:
    """Flatten the box/record subtree rooted at `node_id`.

    Returns `(attrs, records)`:
    - `attrs`: flat `{attribute_name: value}` for every `nodetype: attribute`
      descendant not itself inside a nested `record` (layout `box`/`button`/
      `text` nodes are transparent and merged upward).
    - `records`: `{domain: [attrs_and_nested_records, ...]}` for every
      `nodetype: record` descendant that carries a `domain` -- one dict per
      occurrence, so repeated roles (multiple directors, multiple
      shareholders) naturally become a list.
    """
    if visited is None:
        visited = set()
    attrs: dict = {}
    records: dict = {}
    node = node_map.get(node_id)
    if not isinstance(node, dict):
        return attrs, records
    for child_id in node.get("children", []):
        if child_id in visited:
            continue
        visited.add(child_id)
        child = node_map.get(child_id)
        if not isinstance(child, dict):
            continue
        nodetype = child.get("nodetype")
        if nodetype == "attribute":
            name = child.get("attribute")
            value = child.get("attributeValue")
            if value is None:
                text = child.get("text") or {}
                value = text.get("readonly-value") or text.get("dcText") or text.get("label")
            if name and value is not None:
                attrs[name] = value
        elif nodetype == "record":
            domain = child.get("domain")
            sub_attrs, sub_records = walk_record(child_id, node_map, visited)
            combined = dict(sub_attrs)
            combined.update(sub_records)
            if domain:
                records.setdefault(domain, []).append(combined)
            else:
                attrs.update(sub_attrs)
                for d, lst in sub_records.items():
                    records.setdefault(d, []).extend(lst)
        else:
            # box / button / text / repeater / expando -- pure layout, flatten.
            sub_attrs, sub_records = walk_record(child_id, node_map, visited)
            attrs.update(sub_attrs)
            for d, lst in sub_records.items():
                records.setdefault(d, []).extend(lst)
    return attrs, records


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(r"^(.*) \(([A-Z0-9]+)\)$")


def extract_search_results(node_map: dict) -> list[dict]:
    """From a search-click delta response's node map, return one dict per
    matched entity: `{"nodeId", "label", "name", "registrationNumber",
    **row_attrs}`. `nodeId` is the hyperlink button's node id -- feed it to
    `commands=[{"type": "view-node-button-click", "id": nodeId}]` in the SAME
    session to get the `entityView` redirect URL. Raises `NoResultsFound` if
    the search legitimately matched nothing.

    NOTE: the `searchResults` node's `text.noResults` string ("Your search
    returned no results") is a CSS-hidden-unless-empty template string that
    is present in the delta response REGARDLESS of whether there are real
    matches (confirmed: it's there even alongside 11 real hits) -- do not use
    its presence as a signal. Likewise the repeater's own `kv.ui-count` /
    `ui-display-count` were observed at "0" even in a response carrying 11
    real result rows (looks like a pre-render placeholder, not a live
    count) -- also not usable. The only reliable signal found during recon
    is whether any `Name (REGNUM)`-labeled hyperlink button actually exists
    in the response.
    """
    repeater_id = None
    for node_id, node in node_map.items():
        if isinstance(node, dict) and node.get("widget") == "search-results" and node.get("nodetype") == "repeater":
            repeater_id = node_id
            break
    if repeater_id is None:
        # Not on a search-results screen at all -- shape changed upstream.
        raise UnexpectedShape("no search-results repeater in response")

    results = []
    for node_id, node in node_map.items():
        if not isinstance(node, dict) or node.get("nodetype") != "button":
            continue
        text = node.get("text")
        if not isinstance(text, dict) or "label" not in text:
            continue
        label = text["label"]
        m = _LABEL_RE.match(label)
        if not m:
            continue  # not an entity hyperlink (e.g. the "Cancel"/"Search" buttons)
        row: dict = {"nodeId": node_id, "label": label, "name": m.group(1), "registrationNumber": m.group(2)}
        results.append(row)
    if not results:
        raise NoResultsFound()
    return results


def extract_entity_detail(node_map: dict) -> dict:
    """From an `entityView` page's (clean) view tree, flatten the root
    `Company` record into `{**company_attrs, **role/address record groups}`.
    """
    root_id = node_map.get("root")
    if not root_id or root_id not in node_map:
        raise UnexpectedShape("entityView view tree has no root node")
    root_node = node_map[root_id]
    if root_node.get("domain") != "Company":
        raise UnexpectedShape(f"entityView root domain is {root_node.get('domain')!r}, expected 'Company'")
    attrs, records = walk_record(root_id, node_map)
    if "CompanyNumber" not in attrs:
        raise UnexpectedShape(f"Company record has no CompanyNumber; got attrs keys={sorted(attrs)}")
    result = dict(attrs)
    result.update(records)
    return result


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_detail_record(query: str, entity_view_url: str, detail: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-verne-entityview",
        "_scrapedAt": utc_now_iso(),
        "entityViewUrl": entity_view_url,
        **detail,
    }


def build_summary_record(query: str, row: dict) -> dict:
    row = dict(row)
    row.pop("nodeId", None)  # session-scoped, meaningless outside this run
    return {
        "_input": query,
        "_source": "S1-verne-searchresult",
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
