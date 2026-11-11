---
name: balanced-brace-json
description: "Extract JSON embedded in HTML <script> tags with a balanced-brace walker that survives nested and escaped braces where regex fails. Use when pulling data from __NEXT_DATA__, __APOLLO_STATE__, self.__next_f, window.__* blobs, or any inline JSON-in-HTML."
---

# Balanced-Brace JSON-in-HTML Walker

> **The universal extractor.** Almost every modern site embeds critical data as inline JSON inside `<script>` tags. Regex `/{.*?}/` breaks when the JSON contains escaped braces (`\}`), nested objects, or strings with `}` characters. A balanced-brace walker handles all of these.

## Problem

You need to extract a JSON object from HTML like:

```html
<script>self.__next_f.push([1, '{"props":{"pageProps":{...lots of nested {} ...}}}'])</script>
<script>window.__APOLLO_STATE__ = {"User:123":{"id":"123","posts":{"edges":[...]}}};</script>
<script>window.__cache = {...}</script>
<script>var ytInitialData = {"contents":{...}};</script>
```

Regex approaches fail when:
- The JSON contains escaped quotes inside strings: `"text": "He said \"hello\""`
- The JSON contains literal `}` inside string values: `"emoji": "}"`
- Adjacent `<script>` blocks contain stray braces
- The JSON value is on a single 500KB line (regex backtracking explodes)

## Solution: stateful parser that tracks nesting + string quoting

```python
def extract_balanced_braces(text: str, start: int) -> str | None:
    """
    Given text and the index of the opening '{', return the substring through the matching '}'.
    Handles escaped chars inside strings and nested objects/arrays correctly.
    Returns None if no balanced match (truncated input).
    """
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
                    return text[start:i + 1]
    
    return None  # truncated / unbalanced
```

## Usage patterns

### Pattern 1: extract by anchor string

```python
import json

def extract_json_after(html: str, anchor: str) -> dict | None:
    """Find anchor, then walk balanced braces from the next '{'."""
    pos = html.find(anchor)
    if pos == -1:
        return None
    pos = html.find("{", pos)
    if pos == -1:
        return None
    blob = extract_balanced_braces(html, pos)
    if blob is None:
        return None
    return json.loads(blob)

# Examples:
apollo = extract_json_after(html, "window.__APOLLO_STATE__ = ")
cache  = extract_json_after(html, "window.__cache = ")
ytdata = extract_json_after(html, "var ytInitialData = ")
detail = extract_json_after(html, "window.detailData.globalData = ")
```

### Pattern 2: extract `__NEXT_DATA__` (well-anchored, always works)

```python
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
if m:
    data = json.loads(m.group(1))
```

### Pattern 3: walk multiple inline `<script type="application/json">` blocks (FB / Threads)

```python
def walk_inline_json_blocks(html: str):
    """Yields parsed dict from every <script type="application/json">."""
    for m in re.finditer(
        r'<script[^>]+type="application/json"[^>]*>(.+?)</script>',
        html, re.DOTALL,
    ):
        try:
            yield json.loads(m.group(1))
        except json.JSONDecodeError:
            continue


def find_story_node(html: str, post_id: str) -> dict | None:
    """FB-style: find the inline JSON block whose Story.id matches."""
    for block in walk_inline_json_blocks(html):
        story = _dfs_find(block, lambda v: 
            isinstance(v, dict) and v.get("__typename") == "Story" and v.get("post_id") == post_id
        )
        if story:
            return story
    return None
```

### Pattern 4: DFS walk to find by key

```python
def dfs_find(obj, predicate, max_depth=20):
    """Walk a nested structure and return the first value matching predicate."""
    stack = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            continue
        if predicate(cur):
            return cur
        if isinstance(cur, dict):
            stack.extend((v, depth + 1) for v in cur.values())
        elif isinstance(cur, list):
            stack.extend((v, depth + 1) for v in cur)
    return None

# Find user object by username in Pinterest's __PWS_INITIAL_PROPS__
user = dfs_find(
    pws_state,
    lambda v: isinstance(v, dict) and v.get("username") == "pinterest",
)
```

### Pattern 5: resolve Apollo cache refs

Apollo stores objects flat with `{type: "id", id: "User:123"}` pointers. Resolve recursively.

```python
def resolve_apollo_refs(node, cache, max_depth=15, _depth=0):
    if _depth > max_depth:
        return node
    if isinstance(node, dict):
        if "type" in node and node.get("type") == "id" and "id" in node:
            referenced = cache.get(node["id"])
            return resolve_apollo_refs(referenced, cache, max_depth, _depth + 1)
        return {
            k: resolve_apollo_refs(v, cache, max_depth, _depth + 1)
            for k, v in node.items()
            if k != "__typename"   # strip noise
        }
    if isinstance(node, list):
        return [resolve_apollo_refs(v, cache, max_depth, _depth + 1) for v in node]
    return node
```

## Site-specific anchors

| Site | Anchor | Walker target |
| --- | --- | --- |
| Tokopedia PDP | `window.__cache = ` | Apollo cache, resolve refs |
| Alibaba detail | `window.detailData.globalData = ` (fallback: `.unsafe = `) | flat product object |
| Alibaba search | `window.searchData = ` | listing array |
| StockX | `__APOLLO_STATE__` | resolve refs to find `Product` |
| Medium post | `window.__APOLLO_STATE__ = ` | post in Apollo cache |
| Pinterest | `__PWS_INITIAL_PROPS__` (priority chain: `profile-snippet` → `__PWS_DATA__` → `__PWS_INITIAL_PROPS__` → `initial-state`) | Redux-shaped state |
| Threads | `adp_BarcelonaPostPageDirectQueryRelayPreloader_` | `__bbox.result.data.media` |
| Facebook | inline `<script type="application/json">` blocks | `Story` typename + matching post_id |
| YouTube | `var ytInitialData = ` / `var ytInitialPlayerResponse = ` | structured navigation/player data |
| TikTok SSR | `__UNIVERSAL_DATA_FOR_REHYDRATION__` (current) / `__FRONTITY_CONNECT_STATE__` (legacy embed) / `SIGI_STATE` (older) / `__NEXT_DATA__` (generic Next.js sites) | webapp.video-detail |
| Bloomberg article | `__NEXT_DATA__` primary, `__PRELOADED_STATE__` secondary, LD-JSON tertiary | full story object |
| NYT / WSJ / Barron's | `__NEXT_DATA__` | `pageProps.snippet` / `articleData.flattenedAltSummaries` |
| Investing.com | `__NEXT_DATA__` | `state.newsStore._article` |
| Capterra | `<script type="application/ld+json">` (JSON-LD `SoftwareApplication`/`BreadcrumbList`/`FAQPage`) | typed entities |
| Twitch | not needed (inline GQL) | n/a |
| Telegram | not needed (CSS classes `.tgme_widget_message`) | n/a |

## Anti-XSSI prefix stripping (Google)

Google's internal JSON responses are prefixed with anti-XSSI nonsense:

```
)]}'
{"actual": "json"}
```

```python
def strip_response_prefix(text: str) -> str:
    """Tolerant XSSI-prefix stripper for Google internal responses."""
    for prefix in (")]}'\n\n", ")]}'\n", ")]}'"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text
```

Some Google endpoints (`tbm=map`) are double-wrapped: `text[:-6]` to drop trailing junk, then JSON parse outer, then extract inner from `outer["d"]`, then strip prefix again.

## Caveats

- **Don't use `re.findall(r'\{.*\}', html, re.DOTALL)`** — catastrophic backtracking on long lines, will hang.
- **Always handle `json.JSONDecodeError`** — sites occasionally truncate inline JSON when SSR errors.
- **Apollo cache `__typename` keys add noise** — strip them at resolve time (see Pattern 5).
- **Large blobs (>500KB) are common** in `__PWS_INITIAL_PROPS__`, Apollo state, TikTok SSR. The walker is O(n) so no issue, but allocate enough memory.
- **Multiple anchors can exist** — Alibaba sometimes has both `window.detailData.globalData = {...}` and `window.detailData.unsafe = {...}`. Try fallbacks in order.

## Where used

- Tokopedia Apify + production pipeline (Apollo cache + resolve_refs)
- Alibaba suite (multi-marker detailData)
- TikTok actors + crawler (5-strategy chain)
- Pinterest (PWS state DFS walk)
- Facebook (inline JSON Story walk for post-detail)
- Bloomberg article-scraper (NEXT_DATA + PRELOADED_STATE)
- Online News suite (Investing/NYT/WSJ/Barron's NEXT_DATA)
- YouTube (ytInitialData + ytInitialPlayerResponse)
- Medium post-detail (Apollo state)
- StockX (Apollo via search backdoor)
- Google ecosystem (anti-XSSI prefix stripping)

## See also
- [`skills/apollo-state-paywall.md`](../apollo-state-paywall/SKILL.md)
- [`skills/google-internal-apis.md`](../google-internal-apis/SKILL.md)
