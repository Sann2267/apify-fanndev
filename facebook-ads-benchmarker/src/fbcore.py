"""Shared Facebook transport and structural-parsing helpers.

Three things every Facebook actor in this portfolio needs, none of them obvious
from the outside:

1. **The `__rd_verify` challenge.** Some surfaces -- the Ad Library above all --
   answer the first request with HTTP 403 and a 481-byte body whose only content
   is a script that POSTs to `/__rd_verify_<token>?challenge=3` and reloads.
   Solving it is a single unauthenticated POST; the reply sets an `rd_challenge`
   cookie good for 24h, after which the same URL returns 200 with the full
   payload. Measured 2026-09-20: without the POST, 16/16 TLS profiles get 403
   and no amount of header spoofing helps; with it, a plain chrome131 profile on
   an ordinary home IP gets the complete page. It is a challenge, not an IP ban,
   which is why no proxy is required.

2. **Replaying Facebook's own GraphQL calls.** Facebook server-renders the first
   slice of most feeds into `<script type="application/json">` blocks and leaves
   the rest to the client. The client's query ids are *not* published in the HTML
   as `doc_id`, but the relay preloader block carries
   `{"queryID": ..., "variables": {...}, "queryName": ...}` for every query the
   page kicks off, and a pagination query's id can be read out of the page's own
   JS bundle. Both are harvested at runtime rather than hard-coded, because a
   pinned id dies silently on Facebook's next deploy.

3. **Structural parsing.** Facebook ships ~230 JSON blocks per page and their
   order changes between requests, so nothing here is read by position. Every
   value is found by the key that names it, and a field no marker resolves comes
   out as None rather than being guessed from a neighbour.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import random
import re
import urllib.parse
from typing import Any, Iterator

from curl_cffi.requests import AsyncSession

BASE_URL = "https://www.facebook.com"
GRAPHQL_URL = f"{BASE_URL}/api/graphql/"

# No TLS-fingerprint gate was found on any Facebook surface tested (16/16
# curl_cffi profiles returned the same tier), so the ladder is a courtesy
# rotation for transport hiccups, not a bypass.
TLS_PROFILE = "chrome131"
TLS_LADDER = ["chrome131", "chrome124", "firefox133", "safari17_0", "chrome120"]

NAVIGATE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

# Facebook answers HTTP 200 for things that do not exist. What separates them is
# the size of the body: a payload at or below this threshold carries no entity
# data at all, only the shell. Measured across pages, groups and events on
# 2026-09-20 and byte-stable across three repeats each.
HOLLOW_MAX_BYTES = 450_000

CHALLENGE_PATH = re.compile(r"fetch\('(/__rd_verify_[^']+)'")
JSON_BLOCK = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
PRELOADER = re.compile(
    r'"queryID":"(\d+)","variables":(\{.*?\}),"queryName":"([A-Za-z0-9_]+)"'
)
BUNDLE_SRC = re.compile(r'src="(https://static\.xx\.fbcdn\.net/rsrc\.php/[^"]+\.js[^"]*)"')


class BlockedError(RuntimeError):
    """Facebook refused the request in a way retrying did not fix."""


class FacebookSession:
    """One cookie jar, one TLS profile, challenge solving and GraphQL replay."""

    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        language: str = "en-US",
        timeout: int = 90,
        request_delay: float = 0.6,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.language = language
        self.timeout = timeout
        self.request_delay = request_delay
        self.log = log
        self._session: AsyncSession | None = None
        self._warmed = False
        self._bundle_ids: dict[str, str] = {}
        # Set once Facebook rate-limits a GraphQL call, so the actor can report
        # a short answer as rate-limited rather than as the end of the results.
        self.rate_limited = False

    # -- lifecycle -----------------------------------------------------------
    def _build(self, profile: str) -> AsyncSession:
        kwargs: dict[str, Any] = {"impersonate": profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        return AsyncSession(**kwargs)

    async def __aenter__(self) -> "FacebookSession":
        self._session = self._build(self.profile)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def reset(self, profile: str | None = None) -> None:
        await self.close()
        if profile:
            self.profile = profile
        self._session = self._build(self.profile)
        self._warmed = False

    # -- requests ------------------------------------------------------------
    def _headers(self, referer: str | None) -> dict:
        headers = {**NAVIGATE_HEADERS, "accept-language": f"{self.language},en;q=0.9"}
        if referer:
            headers["referer"] = referer
            headers["sec-fetch-site"] = "same-origin"
        return headers

    async def warmup(self) -> None:
        """Collect the datr/sb cookies an ordinary visitor would already carry."""
        if self._warmed:
            return
        self._warmed = True
        try:
            await self._session.get(BASE_URL + "/", headers=self._headers(None))
        except Exception as exc:
            if self.log:
                self.log.warning(f"warmup failed ({exc}); continuing without it")

    async def _solve_challenge(self, html: str, referer: str) -> bool:
        """POST the `__rd_verify` path the 403 body names. True if one was found."""
        match = CHALLENGE_PATH.search(html)
        if not match:
            return False
        try:
            await self._session.post(
                BASE_URL + match.group(1),
                headers={
                    **self._headers(referer),
                    "accept": "*/*",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                },
            )
        except Exception as exc:
            if self.log:
                self.log.warning(f"challenge POST failed: {exc}")
            return False
        if self.log:
            self.log.info("Solved a Facebook __rd_verify challenge.")
        return True

    async def get_html(self, url: str, referer: str | None = None) -> str:
        """GET a page, solving the verification challenge and retrying transport errors."""
        if self._session is None:
            raise RuntimeError("FacebookSession used outside its async context manager")
        await self.warmup()
        last: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._session.get(
                    url, headers=self._headers(referer), allow_redirects=True
                )
            except Exception as exc:
                last = exc
                await self._backoff(attempt, f"transport error: {exc}")
                continue

            if response.status_code == 200:
                if self.request_delay:
                    await asyncio.sleep(self.request_delay)
                return response.text

            if response.status_code == 403:
                if await self._solve_challenge(response.text, url):
                    continue  # the retry is the point; no backoff needed
                last = BlockedError("HTTP 403 with no solvable challenge")
                await self._backoff(attempt, "HTTP 403")
                continue

            if response.status_code == 404:
                raise BlockedError("HTTP 404 -- Facebook rejected the URL shape")

            if response.status_code in (429, 500, 503):
                last = BlockedError(f"HTTP {response.status_code}")
                nxt = TLS_LADDER[(attempt + 1) % len(TLS_LADDER)]
                await self._backoff(attempt, f"HTTP {response.status_code}; rotating to {nxt}")
                await self.reset(nxt)
                continue

            last = BlockedError(f"HTTP {response.status_code}")
            await self._backoff(attempt, f"HTTP {response.status_code}")

        raise BlockedError(f"retries exhausted: {last}")

    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.4)
        if self.log:
            self.log.warning(f"retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s ({reason})")
        await asyncio.sleep(delay)

    # -- GraphQL replay ------------------------------------------------------
    async def graphql(
        self,
        html: str,
        friendly_name: str,
        doc_id: str,
        variables: dict,
        referer: str,
    ) -> dict:
        """Replay one of the page's own GraphQL queries with our own variables.

        `html` is the document the tokens come from: Facebook binds `lsd` and the
        `__spin_*` revision triple to the served page, so tokens harvested from
        one document are the only ones that work for calls made from it.
        """
        if self._session is None:
            raise RuntimeError("FacebookSession used outside its async context manager")
        tokens = harvest_tokens(html)
        if not tokens.get("lsd"):
            raise BlockedError("no LSD token in the page -- cannot call GraphQL")

        form = {
            "av": "0",
            "__aaid": "0",
            "__user": "0",
            "__a": "1",
            "__req": "7",
            "__hs": tokens.get("hs", ""),
            "dpr": "1",
            "__ccg": "EXCELLENT",
            "__rev": tokens.get("rev", ""),
            "__s": "::",
            "__hsi": tokens.get("spin_t", ""),
            "__comet_req": "15",
            "lsd": tokens["lsd"],
            "jazoest": "2",
            "__spin_r": tokens.get("rev", ""),
            "__spin_b": tokens.get("spin_b", "trunk"),
            "__spin_t": tokens.get("spin_t", ""),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": friendly_name,
            "variables": json.dumps(variables, ensure_ascii=False),
            "server_timestamps": "true",
            "doc_id": doc_id,
        }
        headers = {
            "accept": "*/*",
            "accept-language": f"{self.language},en;q=0.9",
            "content-type": "application/x-www-form-urlencoded",
            "origin": BASE_URL,
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-fb-lsd": tokens["lsd"],
            "x-fb-friendly-name": friendly_name,
            "x-asbd-id": "359341",
        }
        response = await self._session.post(GRAPHQL_URL, headers=headers, data=form)
        if self.request_delay:
            await asyncio.sleep(self.request_delay)
        if response.status_code != 200:
            raise BlockedError(f"GraphQL HTTP {response.status_code}")
        payload = first_json_object(response.text)
        self._note_rate_limit(payload)
        return payload

    def _note_rate_limit(self, payload: dict) -> None:
        """Say so, once, when Facebook rate-limits the pagination query.

        Measured 2026-09-20 on the Apify platform: the server-rendered first page
        is served normally from a datacenter IP, but the very first GraphQL
        pagination call comes back HTTP 200 carrying
        `{"errors": [{"message": "Rate limit exceeded"}]}`. The same run with the
        Apify RESIDENTIAL proxy group enabled paginated fully -- 60 ads over four
        pages against 30 with no proxy.

        Without this notice the symptom is indistinguishable from "the search
        only had 30 results", which is the kind of silent wrong answer this
        portfolio exists to avoid.
        """
        if self.rate_limited:
            return
        errors = payload.get("errors")
        if not isinstance(errors, list):
            return
        for error in errors:
            message = error.get("message") if isinstance(error, dict) else str(error)
            if message and "rate limit" in str(message).lower():
                self.rate_limited = True
                if self.log:
                    self.log.warning(
                        "Facebook answered the pagination query with "
                        f"{message!r}. On the Apify platform this happens on "
                        "datacenter IPs from the first paginated request, while "
                        "the server-rendered first page is unaffected. Enable the "
                        "Apify proxy with the RESIDENTIAL group to page past it."
                    )
                return

    async def bundle_doc_id(self, html: str, query_name: str) -> str | None:
        """Read a pagination query's id out of the page's own JS bundles.

        Facebook stores it as a one-line module:
            __d("<QueryName>_facebookRelayOperation",[],function(...){a.exports="123..."})
        Bundles are fetched once per session and the answer cached, because the
        page that needs page 2 is rarely the last page we will ask for.
        """
        if query_name in self._bundle_ids:
            return self._bundle_ids[query_name] or None
        exact = re.compile(
            re.escape(query_name) + r'_facebookRelayOperation"[\s\S]{0,300}?exports\s*=\s*"(\d{6,})"'
        )
        loose = re.compile(
            re.escape(query_name) + r'_facebookRelayOperation[\s\S]{0,300}?"(\d{6,})"'
        )
        for src in dict.fromkeys(BUNDLE_SRC.findall(html)):
            url = src.replace("&amp;", "&")
            try:
                response = await self._session.get(url, headers={"accept": "*/*"})
            except Exception:
                continue
            if response.status_code != 200 or query_name not in response.text:
                continue
            found = exact.search(response.text) or loose.search(response.text)
            if found:
                self._bundle_ids[query_name] = found.group(1)
                if self.log:
                    self.log.info(f"Harvested doc_id {found.group(1)} for {query_name}.")
                return found.group(1)
        self._bundle_ids[query_name] = ""
        if self.log:
            self.log.warning(
                f"No doc_id found for {query_name} -- pagination beyond the "
                "server-rendered slice is unavailable this run."
            )
        return None


# -- token / preloader harvesting --------------------------------------------
_TOKEN_PATTERNS = {
    "lsd": re.compile(r'"LSD",\[\],\{"token":"(.*?)"'),
    "rev": re.compile(r'"__spin_r":(\d+)'),
    "spin_b": re.compile(r'"__spin_b":"(.*?)"'),
    "spin_t": re.compile(r'"__spin_t":(\d+)'),
    "hs": re.compile(r'"haste_session":"(.*?)"'),
}


def harvest_tokens(html: str) -> dict:
    """Pull the per-document tokens a GraphQL POST has to echo back."""
    out: dict[str, str] = {}
    for key, pattern in _TOKEN_PATTERNS.items():
        match = pattern.search(html)
        if match:
            out[key] = match.group(1)
    return out


def harvest_preloaders(html: str) -> dict[str, tuple[str, dict]]:
    """{queryName: (queryID, variables)} for every query the page preloads.

    This is how a feed query's id is obtained without hard-coding it: the page
    tells us, every time it is served.
    """
    out: dict[str, tuple[str, dict]] = {}
    for query_id, raw_vars, name in PRELOADER.findall(html):
        try:
            out[name] = (query_id, json.loads(raw_vars))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def first_json_object(body: str) -> dict:
    """Decode a GraphQL reply, which may be several JSON documents concatenated.

    Facebook streams deferred fragments as extra newline-separated objects after
    the first. The first holds the query's own data; the rest are fill-ins for
    lazily rendered UI and are kept under `_streamed` so a caller that needs them
    can look, without them ever overwriting the primary document.
    """
    body = (body or "").strip()
    if not body:
        return {}
    decoder = json.JSONDecoder()
    index = 0
    documents: list[dict] = []
    while index < len(body):
        while index < len(body) and body[index] in " \r\n\t":
            index += 1
        if index >= len(body):
            break
        try:
            obj, offset = decoder.raw_decode(body, index)
        except ValueError:
            break
        if isinstance(obj, dict):
            documents.append(obj)
        index = offset
    if not documents:
        return {}
    merged = documents[0]
    if len(documents) > 1:
        merged["_streamed"] = documents[1:]
    return merged


# -- structural parsing -------------------------------------------------------
def iter_json_blocks(html: str) -> Iterator[Any]:
    """Yield every embedded JSON block that parses; malformed blocks are skipped."""
    for raw in JSON_BLOCK.findall(html):
        try:
            yield json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue


def walk(node: Any) -> Iterator[dict]:
    """Depth-first walk yielding every dict in the tree."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def find_nodes(root: Any, *required_keys: str) -> list[dict]:
    """Every dict in `root` carrying all of `required_keys`."""
    return [node for node in walk(root) if all(key in node for key in required_keys)]


def text_of(node: Any) -> str | None:
    """Unwrap Facebook's {text: {..., text: "..."}} envelope."""
    if isinstance(node, str):
        return node or None
    if isinstance(node, dict):
        inner = node.get("text")
        if isinstance(inner, str):
            return inner or None
        if isinstance(inner, dict):
            return text_of(inner)
    return None


COUNT_TEXT = re.compile(r"^([\d][\d.,]*)\s*([KMB])?\b", re.I)
MULTIPLIER = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_count(label: Any) -> int | None:
    """"311K" / "39M followers" / "1,234" -> int. None when the shape is unfamiliar.

    Abbreviated counts are approximations on Facebook's side, so callers keep the
    raw label alongside the number rather than replacing it.
    """
    if label is None:
        return None
    if isinstance(label, bool):
        return None
    if isinstance(label, (int, float)):
        return int(label)
    match = COUNT_TEXT.match(str(label).strip())
    if not match:
        return None
    number, suffix = match.groups()
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        value *= MULTIPLIER[suffix.upper()]
    return int(value)


def unwrap_link(url: str | None) -> str | None:
    """Undo Facebook's l.php redirect wrapper.

    Outbound links are rewritten to l.facebook.com/l.php?u=<encoded>&h=<token>,
    and the token is per-render -- the wrapped URL is not stable between two
    fetches of the same page, which makes it useless as an output field.
    """
    if not url:
        return None
    if "/l.php" not in url and "l.facebook.com" not in url:
        return url
    try:
        query = urllib.parse.urlparse(url).query
        target = urllib.parse.parse_qs(query).get("u", [None])[0]
    except ValueError:
        return url
    return target or url


def decode_b64_id(encoded: Any) -> str | None:
    """Recover a numeric id from one of Facebook's base64 node ids."""
    if not encoded or not isinstance(encoded, str):
        return None
    try:
        decoded = base64.b64decode(encoded + "==", validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None
    found = re.search(r"(\d{8,20})", decoded)
    return found.group(1) if found else None


def og_tag(html: str, prop: str) -> str | None:
    match = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', html)
    return (match.group(1) or None) if match else None


def html_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if not match:
        return None
    cleaned = re.sub(r"\s*\|\s*Facebook\s*$", "", match.group(1)).strip()
    return cleaned or None


def is_hollow(html: str) -> bool:
    """True when Facebook served the shell only -- the entity does not exist.

    Facebook returns HTTP 200 for missing pages, groups and events, so status
    codes cannot tell absence from presence. The body size can: a shell is
    ~330 KB and carries no entity JSON at all.
    """
    return len(html) <= HOLLOW_MAX_BYTES


def dedupe(items: Any) -> list:
    """Order-preserving de-duplication that also copes with dicts and lists."""
    seen: set[str] = set()
    out: list = []
    for item in items or []:
        if isinstance(item, str):
            item = item.strip()
            if not item:
                continue
            key = item
        elif isinstance(item, (dict, list)):
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        else:
            if item is None:
                continue
            key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
