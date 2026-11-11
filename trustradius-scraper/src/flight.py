"""Decoder for the React Server Components "flight" stream that trustradius.com
(Next.js App Router, basePath ``/tr-web-nx``) renders every modern page from.

The same stream arrives two ways:

* with ``RSC: 1`` on the request the server answers ``text/x-component`` -- the
  stream alone, ~40% smaller than the HTML (it matters: every byte goes through
  a residential proxy);
* inside the HTML as ``self.__next_f.push([1, "..."])`` string chunks, which
  concatenate to the identical stream. That is the fallback.

A stream is a sequence of rows ``<hex id>:<payload>``. Most payloads are one
line of JSON, optionally prefixed with a type letter (``I`` module import,
``HL`` preload hint, ``E`` error). Text rows are different: ``<id>:T<hexlen>,``
followed by exactly ``hexlen`` **bytes of UTF-8** with no terminating newline,
so the stream has to be walked as bytes -- splitting on newlines corrupts every
row after the first long review body.

Inside the JSON, strings starting with ``$`` are references: ``$12`` means
"the value of row 0x12", ``$L12`` a lazy client component, ``$undefined`` is
undefined, ``$$`` escapes a literal dollar. Only plain row references carry
data, so :func:`resolve` follows those and leaves the rest as-is.
"""

from __future__ import annotations

import json
import re

_NEXT_F = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.S)
_ROW_ID = re.compile(rb"([0-9a-fA-F]+):")
_REF = re.compile(r"^\$([0-9a-fA-F]+)$")


class FlightError(Exception):
    """The payload is not a flight stream we can read (layout changed)."""


def stream_from_html(html: str) -> str:
    """Concatenate the ``self.__next_f`` chunks of an SSR page."""
    parts: list[str] = []
    for match in _NEXT_F.finditer(html):
        try:
            arr = json.loads(match.group(1))
        except ValueError:
            continue
        if len(arr) > 1 and isinstance(arr[1], str):
            parts.append(arr[1])
    return "".join(parts)


def parse_rows(stream: str) -> dict[str, object]:
    """Split a flight stream into ``{row_id: decoded_value}``.

    Rows that are not data (imports, hints) are kept as raw strings so an id
    still resolves to *something*; nothing downstream reads them.
    """
    data = stream.encode("utf-8")
    rows: dict[str, object] = {}
    pos, end = 0, len(data)
    while pos < end:
        if data[pos : pos + 1] in (b"\n", b"\r"):
            pos += 1
            continue
        m = _ROW_ID.match(data, pos)
        if not m:
            # Not at a row boundary -- skip to the next line rather than fail
            # the whole page on one odd row.
            nl = data.find(b"\n", pos)
            pos = end if nl < 0 else nl + 1
            continue
        row_id = m.group(1).decode().lower()
        pos = m.end()
        if data[pos : pos + 1] == b"T":
            comma = data.find(b",", pos)
            length = int(data[pos + 1 : comma], 16)
            rows[row_id] = data[comma + 1 : comma + 1 + length].decode("utf-8", "replace")
            pos = comma + 1 + length
            continue
        nl = data.find(b"\n", pos)
        nl = end if nl < 0 else nl
        raw = data[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        if raw[:1] in ("[", "{", '"') or raw[:1].isdigit() or raw in ("null", "true", "false"):
            try:
                rows[row_id] = json.loads(raw)
                continue
            except ValueError:
                pass
        rows[row_id] = raw
    if not rows:
        raise FlightError("empty flight stream")
    return rows


def resolve(value, rows: dict[str, object], _depth: int = 0):
    """Replace ``$<id>`` references with the row they point to, recursively."""
    if _depth > 60:
        return value
    if isinstance(value, str):
        m = _REF.match(value)
        if m and m.group(1).lower() in rows:
            return resolve(rows[m.group(1).lower()], rows, _depth + 1)
        if value == "$undefined":
            return None
        if value.startswith("$$"):
            return value[1:]
        if value.startswith("$D"):  # serialised Date
            return value[2:]
        return value
    if isinstance(value, list):
        return [resolve(v, rows, _depth + 1) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, rows, _depth + 1) for k, v in value.items()}
    return value


def walk(value, path=()):
    """Yield ``(node, ancestors)`` for every dict/list in a decoded tree."""
    stack = [(value, path)]
    while stack:
        node, anc = stack.pop()
        if isinstance(node, (dict, list)):
            yield node, anc
            children = node.values() if isinstance(node, dict) else node
            for child in reversed(list(children)):
                if isinstance(child, (dict, list)):
                    stack.append((child, anc + (node,)))


def find_key(rows: dict[str, object], key: str):
    """Every value stored under ``key`` anywhere in the stream, largest first.

    Pages repeat the same object at several depths (a trimmed copy for the
    header, the full one for the body), so callers usually want the biggest.
    """
    found = []
    for row in rows.values():
        if not isinstance(row, (dict, list)):
            continue
        for node, _ in walk(row):
            if isinstance(node, dict) and key in node:
                found.append(node[key])
    found.sort(key=lambda v: len(json.dumps(v, default=str)) if isinstance(v, (dict, list)) else 0, reverse=True)
    return found


def is_element(node) -> bool:
    """A React element serialises as ``["$", type, key, props]``."""
    return isinstance(node, list) and len(node) == 4 and node[0] == "$" and isinstance(node[3], dict)


def class_of(node) -> str:
    return str(node[3].get("className") or "") if is_element(node) else ""


def text_of(node) -> str:
    """Visible text under an element (children strings, depth-first).

    Call it on a RESOLVED tree: there a literal "$49" is a price (it was
    escaped as "$$49" on the wire), so only client references are skipped."""
    out: list[str] = []

    def rec(n):
        if isinstance(n, str):
            if not n.startswith("$L") and n != "$undefined":
                out.append(n)
        elif is_element(n):
            rec(n[3].get("children"))
        elif isinstance(n, list):
            for c in n:
                rec(c)

    rec(node)
    return "".join(out).strip()
