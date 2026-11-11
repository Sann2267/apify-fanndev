---
name: mtop-signed-requests
description: "Build MTOP signed mobile-API requests for the Alibaba family (Alibaba, Taobao, AliExpress, Lazada, Tmall). Use when reviews, mobile-only product data, or h5api.m.* endpoints need an MTOP signature, or when extending an Alibaba-group scraper to a sibling site."
---

# MTOP Signed Requests (Alibaba / Taobao / AliExpress / Lazada Family)

> **Alibaba Group's mobile-API gateway uses a signed request protocol called MTOP.** Once you have it working for one product (Alibaba), the same pattern unlocks the entire family — Taobao, AliExpress, Lazada, Tmall — with only minor parameter swaps.

## Problem

Reviews endpoints, certain product data, and many mobile-app-only features live behind MTOP signed calls:

```
https://h5api.m.alibaba.com/h5/{api.name}/{api.version}/?...
```

Without a valid `sign` header derived from a token + app_key + body, you get `FAIL_SYS_ILLEGAL_ACCESS` or similar.

## Solution: bootstrap token + MD5 signature + auto-discover API name

### Step 1: bootstrap `_m_h5_tk` cookie via throwaway request

The MTOP gateway issues `_m_h5_tk` (`<token>_<timestamp>`) cookie on the first call. You discard this call's response but keep the cookie.

```python
import hashlib, time, json
from curl_cffi.requests import AsyncSession

APP_KEY = "24677475"   # Alibaba — extracted from mobile JS bundle. Different per platform.
GATEWAY = "https://h5api.m.alibaba.com"

async def bootstrap_h5_token(session: AsyncSession) -> str:
    """First call seeds _m_h5_tk cookie. Returns the token portion (before _)."""
    r = await session.get(
        f"{GATEWAY}/h5/mtop.common.getTimestamp/1.0/",
        headers={"Origin": "https://www.alibaba.com", "Referer": "https://www.alibaba.com/"},
    )
    # _m_h5_tk format: "TOKEN_TIMESTAMP"
    cookie = session.cookies.get("_m_h5_tk")
    if not cookie:
        raise RuntimeError("Bootstrap failed — no _m_h5_tk cookie")
    return cookie.split("_")[0]
```

### Step 2: MD5 sign formula

```python
def mtop_sign(token: str, timestamp: int, app_key: str, body: dict) -> str:
    """
    Critical: body must be serialized with NO whitespace (separators=(",", ":")).
    Byte-identical to what's sent in `data` field of the actual POST.
    """
    compact = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    raw = f"{token}&{timestamp}&{app_key}&{compact}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
```

### Step 3: build the signed request

```python
async def mtop_call(session, api_name: str, api_version: str, body: dict, token: str):
    timestamp = int(time.time() * 1000)
    compact_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    sign = mtop_sign(token, timestamp, APP_KEY, body)
    
    params = {
        "jsv":     "2.7.2",
        "appKey":  APP_KEY,
        "t":       str(timestamp),
        "sign":    sign,
        "api":     api_name,
        "v":       api_version,
        "type":    "originaljson",
        "dataType": "json",
        "timeout": "20000",
    }
    
    r = await session.post(
        f"{GATEWAY}/h5/{api_name}/{api_version}/",
        params=params,
        data={"data": compact_body},
        headers={
            "Origin":  "https://www.alibaba.com",
            "Referer": "https://www.alibaba.com/",
        },
    )
    return r.json()
```

### Step 4: auto-discover the right API name (the hard part)

Alibaba doesn't publish MTOP API names. You discover them through:
1. Hunting the mobile bundle for `api: "mtop.xxx.xxx"` patterns
2. Brute-force probing a candidate list against `FAIL_SYS_API_NOT_FOUNDED` vs success
3. Cross-referencing with `taobao.*` and `aliexpress.*` namespaces (often consistent)

```python
REVIEW_API_CANDIDATES = [
    # Alibaba family
    "mtop.alibaba.intl.detail.review.list",
    "mtop.alibaba.product.review.list",
    "mtop.aliexpress.product.review.list",
    # Taobao family
    "mtop.taobao.review.list",
    "mtop.taobao.detail.review",
    # ... 24 candidates total in production
]

async def discover_api_name(session, candidates, body, token):
    """Returns the first candidate that doesn't FAIL_SYS_API_NOT_FOUNDED."""
    for name in candidates:
        for version in ("1.0", "2.0", "3.0"):
            result = await mtop_call(session, name, version, body, token)
            ret = result.get("ret", [])
            if any("FAIL_SYS_API_NOT_FOUNDED" in r for r in ret):
                continue
            return name, version, result
    return None, None, None
```

**As of May 2026, the Alibaba review-list MTOP API is no longer publicly exposed.** 498 combinations (3 gateways × 7 app keys × 24 names) all fail with `FAIL_SYS_API_NOT_FOUNDED`. Production output degrades to AGGREGATE-only with diagnostic `mtopStatus` field (don't silently emit empty reviews — say what failed).

## Per-platform app keys (extracted from JS bundles)

| Platform | App Key | Gateway |
| --- | --- | --- |
| Alibaba | `24677475` | `h5api.m.alibaba.com` |
| Taobao | `12574478` | `h5api.m.taobao.com` |
| AliExpress | `12574478` (shared) | `acs.aliexpress.com` |
| Lazada | varies per country | `acs.lazada.<tld>` |

## Pattern: compact JSON byte-discipline

The sign formula is computed over the JSON-serialized body bytes. If you serialize with `separators=(", ", ": ")` (default `json.dumps`), the bytes you send don't match the bytes you signed → server rejects with `FAIL_SYS_ILLEGAL_REQUEST`.

```python
# RIGHT
body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
sign = hashlib.md5(f"{token}&{ts}&{app_key}&{body_str}".encode()).hexdigest()
# Then send the SAME body_str in the request

# WRONG — server sees different bytes than you signed
body_str_signed = json.dumps(body, separators=(",", ":"))
body_str_sent   = json.dumps(body)                       # has extra spaces!
```

## TLS profile gotcha

Aliyun WAF (`baxia-manager`) issues `_m_h5_tk` cookie **only** for specific Chrome/Safari UAs. Triple-rotation may be needed before bootstrap succeeds:

```python
TLS_PROFILES_FOR_MTOP = ["safari18_0", "safari17_0", "chrome131"]

for profile in TLS_PROFILES_FOR_MTOP:
    session = AsyncSession(impersonate=profile, ...)
    try:
        token = await bootstrap_h5_token(session)
        break
    except RuntimeError:
        continue
else:
    raise RuntimeError("All TLS profiles failed to bootstrap MTOP token")
```

## Caveats

- **App keys rotate every 6–12 months.** When MTOP starts returning `FAIL_SYS_ACCESS_DENIED`, re-extract from a fresh mobile bundle.
- **Token TTL is ~30 minutes.** Re-bootstrap on first auth failure within a long-running scraper.
- **`_m_h5_tk_enc` cookie is unused by MTOP** despite appearing in browser DevTools. Don't waste time replicating it.
- **Timestamp must be in milliseconds, not seconds.** Off by 1000× silently produces sign mismatch.
- **Don't share session across workers.** Each worker bootstraps its own `_m_h5_tk`.
- **Aliyun WAF blocks return HTTP 200** with `_____tmd_____` / `baxia-manager` in body — see [`anti-bot/aliyun.md`](../../anti-bot/aliyun.md).
- **Some APIs need `ttid` parameter** (terminal ID). Common values: `2014@taobaobuyer_android_5.2.0`, `12574478@h5_h5_0.0.0`. When in doubt, try omitting first then adding.

## Where used

- Alibaba review scraper (498-combination discovery attempt; production falls back to AGGREGATE-only)
- Pattern reusable across Taobao / AliExpress / Lazada / Tmall family

## See also
- [`anti-bot/aliyun.md`](../../anti-bot/aliyun.md)
- [`skills/tls-fingerprinting.md`](../tls-fingerprinting/SKILL.md)
- [`playbooks/reverse-engineer-internal-api.md`](../../playbooks/reverse-engineer-internal-api.md)
