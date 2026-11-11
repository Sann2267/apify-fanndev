# TikTok webmssdk (X-Bogus / X-Gnarly)

> **TikTok's web defense layer (webmssdk version 5.1.3-ZTCA as of May 2026) generates two per-request signatures: X-Bogus (legacy, reversible) and X-Gnarly (modern, crypto-heavy). The breakthrough: X-Gnarly is reproducible via a pure-crypto Node sidecar — no browser, no DOM, no remote script.**

## Diagnosis

- Response: `{"status_code": 2146, "status_msg": "Please upgrade TikTok app"}` — TLS fingerprint flagged
- Response: empty body 0 bytes — `ticket_guard` not bootstrapped
- Response header: `tt-ticket-guard-result: 0` — IP-reputation rejection upstream of signature
- Response: HTTP 429 — rate limit (not WAF block per se)
- URL contains `verify.captcha` / `verify.traffic` → CAPTCHA escalation

## Two layers, two solutions

### Layer 1: TLS fingerprint — `curl_cffi chrome110`

`requests` library defaults trigger `status_code: 2146`. `curl_cffi` with **chrome110** specifically is the empirically most reliable profile:

```python
from curl_cffi.requests import AsyncSession

session = AsyncSession(impersonate="chrome110", timeout=30)
# chrome131 is faster rate-limited; chrome110 lasts longer
```

| Profile | Behavior |
| --- | --- |
| `chrome110` | ✅ Most reliable, longest rate-limit window |
| `chrome116`, `chrome120`, `chrome124` | ✅ Works on rotation |
| `chrome131` | ⚠️ Faster rate-limited |
| `requests`/`httpx` default | ❌ Instant `status_code: 2146` |

### Layer 2: signature — X-Bogus (legacy) + X-Gnarly (modern)

#### X-Bogus (URL-derivable, no body needed)

Algorithm reverse-engineered. Pure Python implementation in `shared/xbogus.py` of any TikTok actor — copy-paste reusable.

```python
from xbogus import xbogus_sign

params = {"aid": "1988", "device_platform": "web_pc", ...}
params["X-Bogus"] = xbogus_sign(urlencode(params), user_agent="Mozilla/5.0 ...")
```

#### X-Gnarly (modern, requires body + complex crypto)

The 2026 update added X-Gnarly to webmssdk 5.1.3-ZTCA. **Algorithm sourced from `carcabot/tiktok-xgnarly-decoded` GitHub fork.** Pure crypto, no browser:

- MD5(queryString) + MD5(body) + MD5(UA)
- Timestamp + magic constants + version `"5.1.3-ZTCA"` + SDK `"1.0.0.368"`
- XOR-checksum integer fields
- ChaCha20-variant encode → custom base64 alphabet
- Output: ~332-char string

### Node.js sidecar (recommended approach)

Don't reimplement X-Gnarly in Python — the algorithm is too fiddly. Run a deterministic Node subprocess:

```javascript
// shared/xgnarly.js
const crypto = require("crypto");

function gnarlySign(queryString, body, ua, ubcode = 14) {
    // ... full algorithm targeting webmssdk 5.1.3-ZTCA
    // MD5(queryString), MD5(body), MD5(ua), then ChaCha20 + base64
    return signature;
}

const [, , queryString, body, ua, ubcode] = process.argv;
console.log(gnarlySign(queryString, body, ua, parseInt(ubcode || "14", 10)));
```

```python
import subprocess, json

async def x_gnarly_sign(query_string: str, body: str, ua: str, ubcode: int = 14) -> str:
    proc = await asyncio.create_subprocess_exec(
        "node", "shared/xgnarly.js",
        query_string, body, ua, str(ubcode),
        stdout=subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()
```

**Performance:** ~25ms per call. Acceptable for production rate ceilings.

#### `ubcode` semantics

| Value | When |
| --- | --- |
| `4` | `/explore` endpoint warm-up |
| `14` | `/post`, `/search`, most authenticated calls |

## Dockerfile: Node + Python together

```dockerfile
FROM apify/actor-python:3.12

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y nodejs \
 && node --version

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# shared/xgnarly.js is invoked as subprocess from Python
```

## Session warmup mandatory

Before signed API calls, warm `/explore` to collect cookies + mssdk-sg msToken:

```python
async def init_session(client):
    """Bootstrap cookies + msToken via /explore."""
    r = await client.get("https://www.tiktok.com/explore", impersonate="chrome110")
    # Cookie jar now has tt_csrf_token, msToken, etc.
    return r
```

Token cache lives in-memory + optional disk file. Refresh on signed-call failure.

## Host rotation (60 combinations)

5 API hosts × 3 UA configs × 4 TLS profiles = 60 combinations. On retry, cycle through:

```python
HOSTS = [
    "www.tiktok.com",
    "us.tiktok.com",
    "m.tiktok.com",
    "tiktokv.com",
    "api16-normal-c-useast2a.tiktokv.com",
]
UAS = [DESKTOP_CHROME_UA, MOBILE_IOS_UA, MOBILE_ANDROID_UA]
TLS_PROFILES = ["chrome110", "chrome116", "chrome120", "chrome124"]
```

## The mobile-params-on-web-host trick

**Discovered in `tiktok-crawler`:** sending mobile API parameters to `www.tiktok.com` (the web host, not `tiktokv.com`) bypasses X-Bogus/X-Gnarly entirely for some endpoints:

```python
# WRONG (mobile host requires X-Gorgon + device registration — out of scope)
r = await session.get("https://tiktokv.com/api/comment/list/", params=mobile_params)

# RIGHT (web host accepts mobile params, no signature needed)
r = await session.get(
    "https://www.tiktok.com/api/comment/list/",
    params={
        "aid": "1233",                        # mobile aid
        "device_type": "iPhone13,2",
        "iid": "...",
        ...
    },
    headers={"User-Agent": MOBILE_IOS_UA},
)
```

Works for `/api/comment/list/`, `/api/comment/list/reply/`. Doesn't work for `/api/post/item_list/` (still needs X-Gnarly).

## Required CSRF headers

```python
{
    "X-Secsdk-Csrf-Token": "<from-cookie-or-init>",
    "X-Tt-Csrf-Token": "<from-cookie>",
}
```

Read these from the cookie jar after warm-up.

## Endpoint signature requirements

| Endpoint | Signature needed |
| --- | --- |
| `/explore` | X-Gnarly with `ubcode=4` |
| `/api/post/item_list/` | X-Gnarly + X-Bogus |
| `/api/search/general/full/` | X-Gnarly + X-Bogus |
| `/api/comment/list/` | None (mobile-params-on-web-host trick) |
| `/api/comment/list/reply/` | None (same trick) |
| `/embed/@username` | None (SSR HTML fallback) |
| `oEmbed API` | None (public) |

## What does NOT work

- ❌ Playwright / Selenium / StealthyFetcher — TikTok detects `navigator.webdriver`, `ticket_guard` never bootstraps, X-Gnarly never produced (response body 0 bytes)
- ❌ `_waftokenid` server-signed HMAC-SHA256 with unknown key — cannot be issued without solving JS challenge
- ❌ Re-implementing X-Gnarly in Python (algorithm is intricate; use Node sidecar)
- ❌ Mobile API direct (`tiktokv.com`) — requires X-Gorgon + device-registration handshake out of scope
- ❌ X-Gnarly **per-request RSA-1024/ECDSA-384 signature** — even with the sidecar, some endpoints additionally sign with platform-specific RSA. Cannot be forged without JS engine.

## webmssdk version drift

The webmssdk version evolves: 5.1.0 → 5.1.1 → 5.1.2 → 5.1.3 → 5.1.3-ZTCA over 6 months. When the algorithm version changes, your X-Gnarly sidecar needs updating from the upstream `carcabot/tiktok-xgnarly-decoded` fork.

**Healthcheck:** smoke test once per week; on failure, pull latest sidecar.

## Caveats

- **Local residential IP often returns `tt-ticket-guard-result: 0`** — IP reputation rejects upstream of signature layer. No amount of correct X-Gnarly fixes this. Use Apify datacenter or known-good residential ASN.
- **Private accounts are off-limits** — no anon path. Don't waste cycles on auth scraping.
- **Music endpoints in Creative Center API all return 404.** Only top-3 sounds visible via `__NEXT_DATA__` SSR. JS-paginated rest cannot be replicated HTTP-only.
- **Comments dual-strategy (web + mobile) rotates across 60 combinations.** Don't pin one combo; let the retry logic cycle.
- **PO Token / BotGuard for YouTube transcripts is a similar but separate problem** — same general class, no HTTP-only solution (yet).

## Verified production matrix

| Endpoint | Strategy | Verified |
| --- | --- | --- |
| `/api/comment/list/` | Mobile params on web host | ✅ ~1000 comments/min |
| `/api/comment/list/reply/` | Same | ✅ paginated, dedup overlapping |
| `/explore` (trending) | X-Gnarly ubcode=4 | ✅ 18 items/page, paginated |
| Profile SSR | Universal data extractor | ✅ ~1.8s per profile |
| Posts API (`/api/post/item_list/`) | X-Gnarly ubcode=14 | ⚠️ requires DC IP; residential gets ticket_guard=0 |
| Search API | X-Gnarly ubcode=14 | ⚠️ same, DC IP only |
| Hashtag SSR | Universal data | ✅ via SSR HTML |
| Music (CC API) | — | ❌ all return 404 |

## Where used

- TikTok Apify Actors Collection (8 actors, X-Gnarly integration 2026-05-12)
- TikTok Crawler — TikMine (Beanstalk + Kafka, mobile-params trick)

## See also
- [`stacks/nodejs-crypto-sidecar.md`](../stacks/nodejs-crypto-sidecar.md)
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`skills/cookie-warmup.md`](../skills/cookie-warmup.md)
- [`lessons-learned.md`](../lessons-learned.md) (Playwright/Selenium dead-ends, BotGuard impasse)
