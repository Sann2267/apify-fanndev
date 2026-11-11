"""Parser for the JavaScript literal Discord's SSR pages embed.

discord.com/servers, /servers/{slug}-{id}, /trending-games and /game/{...} are
TanStack Router pages. The route data is streamed into the document as a
seroval-serialized JavaScript expression inside a `<script nonce=...>` tag:

    $_TSR.router=($R=>$R[0]={manifest:void 0,matches:$R[1]=[$R[2]={
        i:"__root__ ",u:1789988515582,s:"success",ssr:!0
    }]})($R["tsr"]);$_TSR.e();document.currentScript.remove()

It is close enough to JSON to be tempting and different enough to punish a
regex. The differences that matter:

    keys are bare identifiers      {rank:1}          not {"rank":1}
    booleans are negated numbers   !0 / !1           not true / false
    undefined is an expression     void 0            not null
    every value carries a marker   $R[7]={...}       not {...}
    strings may hold anything      "We're a \"big\" community, 12:03"

That last one is why this is a tokenizer and not a set of patterns: server
descriptions are free text written by strangers and routinely contain braces,
commas, colons and escaped quotes. Recon found server names containing `{id:`
verbatim, which is enough to derail any bracket-counting approach.

The `$R[n]=` prefixes are seroval's back-reference table. Across every page
type recon sampled, no page contained a single bare `$R[n]` READ -- the table
is written and never used, so the prefixes could simply be stripped. They are
resolved properly anyway: seroval emits a back-reference the moment a payload
repeats a subtree, and a discovery listing that happened to show the same
server twice would start doing exactly that, silently, with no version bump to
warn anyone. Resolving costs a dict lookup and removes the whole class of bug.
"""

from __future__ import annotations

import re
from typing import Any

# The SSR payload is always the largest nonce'd inline script. The other two
# are window.GLOBAL_ENV (~360 bytes) and Cloudflare's challenge bootstrap
# (~1 KB), both far smaller than even an empty route payload.
_SCRIPT_RE = re.compile(
    r"<script[^>]*\bnonce=\"[^\"]*\"[^>]*>(.*?)</script>", re.S
)

_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
_REF_RE = re.compile(r"\$R\[(\d+)\]")

_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t", "v": "\v", "0": "\0",
}


class SerializedParseError(ValueError):
    """The embedded payload was not in the shape this parser understands."""


def extract_ssr_script(html: str) -> str:
    """Return the inline script that carries the route payload.

    Raises rather than returning "" so that a page which silently stopped
    embedding its data -- a redirect to a login wall, a Cloudflare interstitial
    served with HTTP 200 -- fails loudly instead of being reported as a server
    with no fields.
    """
    blocks = _SCRIPT_RE.findall(html or "")
    if not blocks:
        raise SerializedParseError(
            "no nonce'd inline script in the document; the page did not render "
            "its route data (redirect, challenge, or a layout change)"
        )
    script = max(blocks, key=len)
    if "$R[" not in script:
        raise SerializedParseError(
            "the largest inline script carries no $R[...] payload "
            f"(len={len(script)}); Discord may have changed its SSR format"
        )
    return script


class _Reader:
    """A cursor over the literal, with one value-parsing method per token."""

    __slots__ = ("src", "pos", "refs")

    def __init__(self, src: str) -> None:
        self.src = src
        self.pos = 0
        self.refs: dict[int, Any] = {}

    # -- primitives --------------------------------------------------------

    def _error(self, what: str) -> SerializedParseError:
        near = self.src[max(0, self.pos - 40):self.pos + 40]
        return SerializedParseError(f"{what} at offset {self.pos}: ...{near}...")

    def _skip_ws(self) -> None:
        src, n = self.src, len(self.src)
        while self.pos < n and src[self.pos] in " \t\r\n":
            self.pos += 1

    def _literal(self, text: str) -> bool:
        if self.src.startswith(text, self.pos):
            self.pos += len(text)
            return True
        return False

    def _string(self) -> str:
        quote = self.src[self.pos]
        self.pos += 1
        out: list[str] = []
        src, n = self.src, len(self.src)
        start = self.pos
        while self.pos < n:
            ch = src[self.pos]
            if ch == quote:
                out.append(src[start:self.pos])
                self.pos += 1
                return "".join(out)
            if ch != "\\":
                self.pos += 1
                continue
            out.append(src[start:self.pos])
            self.pos += 1
            esc = src[self.pos]
            if esc == "u":
                # \uXXXX, including surrogate pairs, which Discord uses heavily
                # for emoji in server names and reasons-to-join.
                code = int(src[self.pos + 1:self.pos + 5], 16)
                self.pos += 5
                if 0xD800 <= code <= 0xDBFF and src.startswith("\\u", self.pos):
                    low = int(src[self.pos + 2:self.pos + 6], 16)
                    if 0xDC00 <= low <= 0xDFFF:
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                        self.pos += 6
                out.append(chr(code))
            elif esc == "x":
                out.append(chr(int(src[self.pos + 1:self.pos + 3], 16)))
                self.pos += 3
            elif esc in ("\n", "\r"):
                # A line continuation contributes nothing.
                self.pos += 1
            else:
                out.append(_ESCAPES.get(esc, esc))
                self.pos += 1
            start = self.pos
        raise self._error("unterminated string")

    def _key(self) -> str:
        ch = self.src[self.pos]
        if ch in "\"'":
            return self._string()
        if ch == "[":
            # A computed key. Not emitted by seroval today; parse it rather
            # than crash if it ever is.
            self.pos += 1
            key = self.value()
            self._skip_ws()
            if not self._literal("]"):
                raise self._error("unclosed computed key")
            return str(key)
        m = _IDENT_RE.match(self.src, self.pos)
        if m:
            self.pos = m.end()
            return m.group(0)
        # Numeric literal keys, which JavaScript coerces to strings. The
        # aggregateFacets map on /servers is keyed this way -- {0:32,1:24579,...}
        # counts servers per category id -- and an identifier-only key parser
        # dies on the very payload that carries the directory's facet totals.
        m = _NUMBER_RE.match(self.src, self.pos)
        if m:
            self.pos = m.end()
            return m.group(0)
        raise self._error("expected an object key")

    # -- containers --------------------------------------------------------

    def _array(self) -> list[Any]:
        self.pos += 1  # [
        out: list[Any] = []
        while True:
            self._skip_ws()
            if self._literal("]"):
                return out
            if self._literal(","):
                # A hole, as in [1,,3]. JavaScript calls it undefined.
                out.append(None)
                continue
            out.append(self.value())
            self._skip_ws()
            if self._literal(","):
                continue
            if self._literal("]"):
                return out
            raise self._error("expected , or ] in array")

    def _object(self) -> dict[str, Any]:
        self.pos += 1  # {
        out: dict[str, Any] = {}
        while True:
            self._skip_ws()
            if self._literal("}"):
                return out
            key = self._key()
            self._skip_ws()
            if not self._literal(":"):
                raise self._error(f"expected : after key {key!r}")
            self._skip_ws()
            out[key] = self.value()
            self._skip_ws()
            if self._literal(","):
                continue
            if self._literal("}"):
                return out
            raise self._error("expected , or } in object")

    # -- dispatch ----------------------------------------------------------

    def value(self) -> Any:
        self._skip_ws()
        if self.pos >= len(self.src):
            raise self._error("unexpected end of payload")

        # $R[7]=<value> assigns and evaluates; a bare $R[7] reads back.
        m = _REF_RE.match(self.src, self.pos)
        if m:
            self.pos = m.end()
            idx = int(m.group(1))
            self._skip_ws()
            if self._literal("="):
                # Register the slot BEFORE parsing the body so a self-
                # referential structure resolves to the container rather than
                # recursing forever. Containers are filled in place.
                placeholder: Any = None
                self.refs[idx] = placeholder
                parsed = self.value()
                self.refs[idx] = parsed
                return parsed
            if idx in self.refs:
                return self.refs[idx]
            raise self._error(f"back-reference $R[{idx}] used before assignment")

        ch = self.src[self.pos]
        if ch == "{":
            return self._object()
        if ch == "[":
            return self._array()
        if ch in "\"'":
            return self._string()
        if ch == "!":
            # seroval writes booleans as !0 (true) and !1 (false).
            if self._literal("!0"):
                return True
            if self._literal("!1"):
                return False
            raise self._error("unrecognised ! expression")
        if self._literal("void 0"):
            return None
        if self._literal("null"):
            return None
        if self._literal("true"):
            return True
        if self._literal("false"):
            return False
        if self._literal("undefined"):
            return None
        num = _NUMBER_RE.match(self.src, self.pos)
        if num:
            self.pos = num.end()
            text = num.group(0)
            if text.lower().startswith(("0x", "-0x")):
                return int(text, 16)
            if "." in text or "e" in text.lower():
                return float(text)
            return int(text)
        raise self._error("unrecognised token")


def parse_router_payload(html: str) -> dict[str, Any]:
    """Parse an SSR page and return the router object it embeds.

    The returned dict is the `$R[0]` value -- `{manifest, matches:[...]}` --
    with every `$R[n]=` marker resolved away.
    """
    script = extract_ssr_script(html)
    anchor = script.find("$_TSR.router=")
    if anchor == -1:
        raise SerializedParseError(
            "no $_TSR.router assignment in the inline script"
        )
    # Skip the `($R=>` arrow wrapper to land on the payload itself.
    start = script.find("$R[", anchor)
    if start == -1:
        raise SerializedParseError("no $R[...] value after $_TSR.router=")
    reader = _Reader(script)
    reader.pos = start
    value = reader.value()
    if not isinstance(value, dict):
        raise SerializedParseError(
            f"router payload parsed as {type(value).__name__}, expected an object"
        )
    return value


def route_loaders(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every route match's loader data, outermost first.

    TanStack nests one entry per route segment. The root match carries only
    feature flags; the data this actor wants is always in the last match that
    has a non-empty `l`. Returning all of them lets callers pick by shape
    instead of by index, which survives Discord adding a layout route.
    """
    out: list[dict[str, Any]] = []
    for match in payload.get("matches") or []:
        if not isinstance(match, dict):
            continue
        loader = match.get("l")
        if isinstance(loader, dict) and loader:
            out.append(loader)
    return out


def find_loader(html: str, *keys: str) -> dict[str, Any]:
    """Parse `html` and return the first loader carrying any of `keys`.

    Raises SerializedParseError naming what was actually present, so a page
    whose shape changed produces a diagnostic a human can act on rather than a
    KeyError.
    """
    loaders = route_loaders(parse_router_payload(html))
    for loader in loaders:
        if any(key in loader for key in keys):
            return loader
    seen = sorted({k for loader in loaders for k in loader})
    raise SerializedParseError(
        f"no route loader carried any of {keys}; loaders held {seen or '(nothing)'}"
    )
