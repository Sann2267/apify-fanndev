"""Parsing of Instagram's server-rendered Relay payload.

Instagram embeds its logged-out data in `<script type="application/json">`
islands. The useful payload sits at a path like::

    require[0][3][0].__bbox.require[0][3][1].__bbox.result.data.<root_key>

Rather than hard-code that path -- it is an implementation detail of Meta's
bootloader and shifts between routes -- everything here walks the parsed tree
looking for the `result.data` shape and collects whatever root keys it finds.
The same walker then works unchanged on the `/api/graphql/` replay response,
whose body is just `{"data": {...}}`.

One thing worth stating because it cost a debugging round: **walk lists in
full**. The payload nests under index 3 of a list, so a walker that samples
`items[:3]` finds nothing and reports the surface as empty.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_ISLAND_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
_LSD_RE = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"\}')
# queryID / variables / queryName always appear together in the preload list.
_PRELOAD_RE = re.compile(r'"queryID":"(\d+)","variables":(\{.*?\}),"queryName":"(\w+)"')

_MAX_DEPTH = 24


class RelayShapeError(Exception):
    """The page parsed, but carried none of the Relay payload we expect."""


def iter_islands(html: str) -> Iterator[dict]:
    """Yield every JSON island that parses and could hold a Relay result."""
    for raw in _ISLAND_RE.findall(html):
        if '"result"' not in raw:
            continue
        try:
            yield json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            # Islands also carry non-Relay config blobs; skipping a malformed
            # one is normal and must not abort the page.
            continue


def collect_data_roots(node: Any, out: list[tuple[str, Any]] | None = None, depth: int = 0) -> list[tuple[str, Any]]:
    """Collect every `(root_key, payload)` sitting under a `result.data` dict."""
    if out is None:
        out = []
    if depth > _MAX_DEPTH:
        return out
    if isinstance(node, dict):
        result = node.get("result")
        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            for key, value in result["data"].items():
                out.append((key, value))
        for value in node.values():
            collect_data_roots(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:  # full list -- see module docstring
            collect_data_roots(value, out, depth + 1)
    return out


def ssr_roots(html: str) -> list[tuple[str, Any]]:
    """Every Relay data root server-rendered into the page."""
    roots: list[tuple[str, Any]] = []
    for island in iter_islands(html):
        collect_data_roots(island, roots)
    return roots


def pick_root(roots: list[tuple[str, Any]], key: str, must_have: str | None = None) -> Any:
    """The payload for `key`, optionally requiring a field to disambiguate.

    A profile page renders `xig_user_by_username` twice -- once with the
    profile fields, once with the timeline connection -- so callers say which
    of the two they mean via `must_have`.
    """
    for root_key, payload in roots:
        if root_key != key or not isinstance(payload, dict):
            continue
        if must_have is None or must_have in payload:
            return payload
    return None


def harvest_lsd(html: str) -> str | None:
    """The per-page-load anti-XSRF nonce. Required in the replay form body."""
    match = _LSD_RE.search(html)
    return match.group(1) if match else None


def harvest_preloads(html: str) -> list[dict]:
    """Every Relay query the page preloaded, with its id and exact variables.

    This is what makes the actor self-healing against doc_id rotation: the id
    comes from the page being scraped, so a Meta redeploy is picked up on the
    next request instead of breaking a pinned constant.
    """
    preloads = []
    for query_id, raw_vars, name in _PRELOAD_RE.findall(html):
        try:
            variables = json.loads(raw_vars)
        except (ValueError, json.JSONDecodeError):
            continue
        preloads.append({"doc_id": query_id, "variables": variables, "name": name})
    return preloads


def find_preload(html: str, name_contains: str) -> dict | None:
    """The preload whose query name contains `name_contains`, if any."""
    wanted = name_contains.lower()
    for preload in harvest_preloads(html):
        if wanted in preload["name"].lower():
            return preload
    return None


def find_connection(node: Any, depth: int = 0) -> dict | None:
    """The first `{edges, page_info}` dict anywhere in a payload."""
    if depth > _MAX_DEPTH:
        return None
    if isinstance(node, dict):
        if "edges" in node and "page_info" in node:
            return node
        for value in node.values():
            found = find_connection(value, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_connection(value, depth + 1)
            if found is not None:
                return found
    return None


def connection_nodes(connection: dict | None) -> list[dict]:
    """`edges[].node` as a plain list, tolerating malformed edges."""
    if not isinstance(connection, dict):
        return []
    nodes = []
    for edge in connection.get("edges") or []:
        if isinstance(edge, dict) and isinstance(edge.get("node"), dict):
            nodes.append(edge["node"])
    return nodes


def next_cursor(connection: dict | None) -> str | None:
    """The cursor to pass as `after`, or None when the connection is exhausted."""
    if not isinstance(connection, dict):
        return None
    page_info = connection.get("page_info")
    if not isinstance(page_info, dict) or not page_info.get("has_next_page"):
        return None
    cursor = page_info.get("end_cursor")
    return cursor if isinstance(cursor, str) and cursor else None
