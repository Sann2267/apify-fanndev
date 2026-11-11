---
name: google-internal-apis
description: "Scrape Google products (Search, News, Trends, Play, Shopping, Photos, Maps, Ads Transparency) via their internal batchexecute RPC and pb= protobuf protocols, no API key or OAuth. Use when building or fixing any Google-property scraper."
---

# Google Internal APIs: `batchexecute` RPC + `pb=` Protobuf

> **Google's internal services (Search, News, Trends, Play, Photos, Shopping, Jobs, Maps, Ads Transparency) all expose two universal protocols.** Once you understand them, you can scrape 11+ Google products without an API key, OAuth, or quota.

## Two protocols cover (almost) everything

| Protocol | Used by | Description |
| --- | --- | --- |
| `batchexecute` RPC | Trends, News, Play, Shopping, Photos, parts of Maps | Universal internal RPC: `POST /_/{Service}Ui/data/batchexecute?rpcids=<RPC_ID>` |
| `pb=` protobuf | Maps (places, reviews, photos, directions) | Flat URL-safe protobuf serialization in query string |

Plus auxiliary patterns: `AF_initDataCallback()` regex for SERP/Play embedded JSON, RSS feed for News bypass, public-key REST for Ads Transparency.

---

## Protocol 1: `batchexecute` RPC

### Endpoint shape

```
POST https://{host}/_/{Service}Ui/data/batchexecute?rpcids={RPC_ID}&...
Content-Type: application/x-www-form-urlencoded

f.req=[[["{RPC_ID}","{nested_json_string}",null,"generic"]]]
```

The `nested_json_string` is a JSON-encoded array of arguments specific to the RPC. The outer envelope is universal.

### Known RPC IDs (production-tested)

| Service | RPC ID | Endpoint host | Use |
| --- | --- | --- | --- |
| Trends | `i0OFE` | `trends.google.com` | Trending searches by geo |
| News | `Ftbldf` | `news.google.com` | Article search (fallback for RSS) |
| Play Reviews | `UsvDTd` | `play.google.com` | App reviews paginated |
| Play (batch app info) | `Ws7gDc` | `play.google.com` | Multiple app metadata in one call |
| Play search | `lGYRle` | `play.google.com` | App keyword search |
| Photos pagination | `lcxiM` | `photos.google.com` | Album photos paginated |
| Shopping | `rFp7Od` | `www.google.com/shopping` | Product details |

### Session token requirement

Most batchexecute endpoints need two session tokens harvested from the service's HTML homepage:

```python
import re

async def harvest_session_tokens(session, service_homepage: str) -> dict:
    r = await session.get(service_homepage)
    return {
        "FdrFJe": re.search(r'"FdrFJe":"(\d+)"', r.text).group(1),     # session id (sid)
        "cfb2h":  re.search(r'"cfb2h":"([^"]+)"', r.text).group(1),    # block ledger (bl)
    }


async def call_batchexecute(session, host: str, service_ui: str, rpc_id: str, payload: list, sid: str, bl: str):
    body = {
        "f.req": json.dumps([[[rpc_id, json.dumps(payload), None, "generic"]]]),
    }
    params = {
        "rpcids":   rpc_id,
        "source-path": "/",
        "f.sid":    sid,
        "bl":       bl,
        "hl":       "en",
        "soc-app":  "162",
        "soc-platform": "1",
        "soc-device":   "1",
        "_reqid":   str(random.randint(100000, 999999)),
        "rt":       "c",
    }
    r = await session.post(
        f"https://{host}/_/{service_ui}/data/batchexecute",
        params=params,
        data=body,
        headers={"x-same-domain": "1", "origin": f"https://{host}", "referer": f"https://{host}/"},
    )
    return r.text
```

### Universal response parser

The response is a wrapped, line-delimited format with anti-XSSI prefix. One regex decodes any service:

```python
def strip_xssi_prefix(text: str) -> str:
    for prefix in (")]}'\n\n", ")]}'\n", ")]}'"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def parse_batchexecute(raw: str, rpc_id: str) -> list | None:
    """Returns the parsed JSON array for the given rpc_id from a batchexecute response."""
    raw = strip_xssi_prefix(raw)
    m = re.search(
        rf'\["wrb\.fr","{re.escape(rpc_id)}","(.*?)(?:",null,null,null,"generic"\])',
        raw,
        re.DOTALL,
    )
    if not m:
        return None
    return json.loads(m.group(1))     # the inner array is the actual payload
```

### Embedded JSON variants (`AF_initDataCallback`)

For Play / Photos / Maps SERP embedded data, parse this pattern in HTML:

```python
def extract_af_data(html: str, key: str) -> dict | None:
    """E.g. key='ds:7' for Play reviews fallback."""
    m = re.search(
        rf"AF_initDataCallback\(\{{key:'{re.escape(key)}',\s*hash:'[^']+',\s*data:(.+?),\s*sideChannel:",
        html,
        re.DOTALL,
    )
    if not m:
        return None
    return json.loads(m.group(1))
```

Known keys:
- `ds:0`/`ds:5`/`ds:6` — Play app info
- `ds:7` — Play reviews (fallback when `UsvDTd` batchexecute fails with "authentication required")

### Multi-locale routing

Every Google request carries `hl` (language) and `gl` (country) — they affect ranking, prices, and even response shape:

```python
params["hl"] = "en"      # language
params["gl"] = "US"      # geo bias (country)
```

---

## Protocol 2: Maps `pb=` flat protobuf

### Format

```
!<index><type><value>!<index><type><value>!...
```

Separator is `!`. Each token = `<index>` (decimal field number), `<type>` (one char), `<value>`.

| Type | Meaning | Example |
| --- | --- | --- |
| `s` | string | `!1s2026Bali` |
| `i` | integer | `!2i20` |
| `d` | double | `!3d-8.4095` |
| `b` | boolean (0/1) | `!4b1` |
| `e` | enum | `!3e2` |
| `y` | **signed int64 big-endian** | `!1y3343949648895870587` |
| `m<N>` | begin sub-message with N fields | `!4m5` (start sub-message with 5 fields) |

### Why `y` matters: Feature IDs

Google Maps places have a Feature ID like `0x2e69fbc427e3767b:0x1f42acba2ea1c621` — two int64s concatenated by colon. The reviews endpoint requires the FID as TWO `y`-typed fields:

```python
import struct

def fid_to_int64s(fid: str) -> tuple[int, int]:
    """'0x2e69fbc427e3767b:0x1f42acba2ea1c621' → (signed_int64_a, signed_int64_b)"""
    a_hex, b_hex = fid.split(":")
    a = struct.unpack(">q", bytes.fromhex(a_hex[2:].zfill(16)))[0]
    b = struct.unpack(">q", bytes.fromhex(b_hex[2:].zfill(16)))[0]
    return a, b


# CRITICAL: use !1y/!2y, NOT !1s. Strings won't work.
a, b = fid_to_int64s("0x2e69fbc427e3767b:0x1f42acba2ea1c621")
pb = f"!1m2!1y{a}!2y{b}!2m2!1i{offset}!2i{limit}!3e{sort}!4m5!3b1!4b1!5b1!6b1!7b1!5m2!1s{kEI}!7e81"
```

### `modify_pb()` helper — split, mutate by index, rejoin

Templates are captured from DevTools and mutated per-call:

```python
def modify_pb(template: str, mutations: dict[int, tuple[str, str]]) -> str:
    """
    Mutate fields by 1-based index.
    mutations = {2: ("s", "new_value"), 17: ("d", "37.7749"), ...}
    """
    tokens = template.split("!")    # tokens[0] is "" (leading !), tokens[i] = "<index><type><value>" for i>=1
    
    for idx, (typ, val) in mutations.items():
        # find token with leading <idx><type> prefix
        for i, tok in enumerate(tokens[1:], start=1):
            if tok.startswith(f"{idx}{typ}"):
                tokens[i] = f"{idx}{typ}{val}"
                break
    
    return "!".join(tokens)
```

### Reviews endpoint pb template (verified 2026-05-12)

```python
# Sort enum: 1=relevant, 2=newest, 3=highest, 4=lowest
# Note: limit > 10 ignored by Google
PB_REVIEWS = (
    "!1m2"
    "!1y{a}"            # FID first int64 (SIGNED!)
    "!2y{b}"            # FID second int64
    "!2m2"
    "!1i{offset}"       # OFFSET-based pagination (not cursor)
    "!2i{limit}"        # capped at 10
    "!3e{sort}"         # sort enum
    "!4m5!3b1!4b1!5b1!6b1!7b1"  # include flags
    "!5m2"
    "!1s{kEI}"          # session token
    "!7e81"
)
```

### Anti-XSSI prefix

Maps responses are prefixed with `)]}'` (4 chars, no newline often) — strip before JSON parse. `tbm=map` SERP responses are **double-wrapped**:

```python
def parse_tbm_map_response(text: str) -> dict:
    text = text.rstrip()
    text = text[:-6]            # drop trailing junk
    outer = json.loads(text)
    inner_raw = outer["d"]
    inner_raw = strip_xssi_prefix(inner_raw)
    return json.loads(inner_raw)
```

### `kEI` session token harvesting

Reviews pb embeds the `kEI` session string (field 19). Harvest from `/maps/place/data=...` HTML:

```python
def harvest_kEI(html: str) -> str | None:
    m = re.search(r"var kEI='([^']+)'", html)
    if m: return m.group(1)
    m = re.search(r'"k":"([^"]+)"', html)   # window.WIZ_global_data.k variant
    if m: return m.group(1)
    return None
```

`kEI` rotates per page-load, lives several minutes per session. Refresh on 401/`/sorry` redirect.

---

## Auxiliary patterns

### News dual-strategy

```python
# Strategy A (preferred): RSS — no anti-bot, fastest
RSS_URL = "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={gl}:{hl}"

# Strategy B (fallback): batchexecute Ftbldf
# Same pattern as other batchexecute calls
```

### Ads Transparency public-key REST

Ads Transparency frontend is React SPA with a hardcoded public browser key in the JS bundle:

```python
ADS_TRANSPARENCY_KEY = "AIzaSyDKDzSzcHU0T5BN5_fH5uyAmfT1b4K8M1U"
# GET https://adstransparency.google.com/.../?key=<ADS_TRANSPARENCY_KEY>
```

### Suggest API (multi-strategy)

```python
# 3 client variants — try in order until 200:
SUGGEST_VARIANTS = [
    "https://suggestqueries.google.com/complete/search?client=firefox&q={q}&hl={hl}",      # JSON array
    "https://suggestqueries.google.com/complete/search?client=psy-ab&q={q}&hl={hl}",       # toolbar
    "https://suggestqueries.google.com/complete/search?client=toolbar&q={q}&output=xml",   # XML
]
```

### SERP triggers (URL query params)

| Service | Trigger param |
| --- | --- |
| Maps | `tbm=map` |
| Shopping | `tbm=shop` |
| News | `tbm=nws` |
| Jobs | `ibp=htl;jobs` |

---

## Risk matrix (Apify residential required?)

| 🟢 No anti-bot | 🟡 Datacenter OK | 🔴 Residential required |
| --- | --- | --- |
| News RSS | Trends batchexecute (low risk) | SERP organic (reCAPTCHA v3) |
| Play App Info AF_initDataCallback | Play Reviews via AF[ds:7] | Maps Places/Reviews |
| Ads Transparency public key | | Shopping (tbm=shop) |
| Suggest API | | Jobs (ibp=htl;jobs) |

## Caveats

- **`UsvDTd` batchexecute Play Reviews returns "authentication required" intermittently.** Fall back to embedded HTML `AF[ds:7]` regex — it works without batchexecute.
- **kEI rotates faster than session_id.** When you get an empty-array response from reviews, re-harvest kEI before retrying.
- **`!3e1` (sort=relevant) returns `[null,null,null,null,null,null,1]`** from IPs outside US-locale. Auto-fallback to `!3e2` (newest) and retry.
- **pb template instability:** Google can shift indexes anytime. Keep `templates.py` modular (one template per endpoint) so updates are localized.
- **`bl` (block ledger) token has its own TTL** independent of `sid`. If sid+bl returns 401 but page HTML works, re-harvest just bl.
- **TLS impersonation is required** for SERP and Maps even from residential — `primp chrome_146` or `curl_cffi chrome146` confirmed.

## Where used

- Google ecosystem suite (11 services, batchexecute RPC IDs mapped)
- Google Maps Apify suite v2.0 (11 actors, pb manipulation, reviews endpoint breakthrough)
- Google Trends batchexecute (533 items in 200.6 ms — fastest)
- News dual-strategy (RSS primary, Ftbldf fallback)

## See also
- [`skills/balanced-brace-json.md`](../balanced-brace-json/SKILL.md) (anti-XSSI prefix stripping)
- [`skills/cookie-warmup.md`](../cookie-warmup/SKILL.md) (Google NAVIGATE_HEADERS vs BROWSER_HEADERS)
