# PerimeterX / HUMAN Security

> **PerimeterX (now HUMAN) is the highest-effort modern bot defense.** It combines JA3/JA4 fingerprinting + behavioral telemetry + IP reputation scoring + a bytecode VM JS challenge (`_px3` / `_pxhd` cookies). For HTTP scraping, the wins come from picking a TLS profile they haven't fingerprinted yet — not from spoofing JS.

## Diagnosis

- Response sets cookies: `_px3`, `_pxhd`, `_pxvid`, `pxcts`
- Response sets cookie: `__Secure-session_id` (on Skyscanner/Bloomberg)
- 403 body contains `Please verify you are a human` or PerimeterX challenge page
- 429 with `x-px-action-token` header
- 200 with `tosv.html` body (Bloomberg ToS-violation soft block)
- Looks like Cloudflare at first — check for `_px3` cookie to disambiguate.

## Bypass strategies (verified production)

### Strategy 1: `scrapling safari2601` — Bloomberg breakthrough

The single most valuable PerimeterX discovery: **Safari 26.0.1** released after PerimeterX's last public fingerprint refresh. `scrapling` ships this profile; `curl_cffi` and `primp` do not.

```python
from scrapling.fetchers import Fetcher

r = Fetcher().get(
    "https://www.bloomberg.com/news/articles/...",
    impersonate="safari2601",
    stealthy_headers=True,
)
# 200 OK from Apify datacenter IP — no residential proxy needed
```

**Verified working:**
- Bloomberg article-scraper (full extraction from datacenter)
- Bloomberg news-feed (RSS + sitemap discovery)
- Bloomberg news-search (deep pagination after additional layers — see below)

### Strategy 2: `curl_cffi` profile ladder — Zillow

For Zillow, no single profile lasts the whole run. Ladder rotation gives ~5–10 burn-tolerant profiles before exhaustion:

```python
ZILLOW_TLS_LADDER = [
    "chrome136",   # baseline
    "chrome142",
    "chrome146",
    "safari260",
]
# Blocklisted (do NOT use):
# - chrome120 (stale, instant block)
```

Combined with multi-step warmup:

```python
async def zillow_warmup(session, region_slug: str):
    await session.get("https://www.zillow.com/")
    await asyncio.sleep(random.uniform(0.7, 1.4))
    await session.get(f"https://www.zillow.com/{region_slug}/")
    # Now JSON API is accessible
```

### Strategy 3: 5-layer evolution — Bloomberg deep pagination

For PerimeterX endpoints that pass single requests but block deep pagination (`nemo-next/api/search/query`), use the full evolution:

**Layer 1 — Primer fetch:** GET HTML page before the API call to seed cookies via the same TCP connection pool.

```python
# WRONG — direct API call, 403
r = await session.post(SEARCH_API, json={...})

# RIGHT — primer first
await session.get("https://www.bloomberg.com/search")
r = await session.post(SEARCH_API, json={...})    # now 200
```

**Layer 2 — Dynamic session proxy rotation:** On 403 mid-run, force fresh residential IP by re-generating `session_id`:

```python
def fresh_residential_url() -> str:
    sid = "s" + secrets.token_hex(8)
    return f"http://groups-RESIDENTIAL,session-{sid}:{APIFY_PROXY_PASSWORD}@proxy.apify.com:8000"
```

**Layer 3 — Fetcher environment isolation:** Re-instantiate the entire `Fetcher()` to drop the keep-alive connection and stale cookies:

```python
async def hard_reset(pool):
    await pool.session.close()
    import gc; gc.collect()
    pool.session = AsyncSession(impersonate=pool.current_profile, ...)
```

**Layer 4 — TLS profile randomization within session:** Per-attempt random pick from a working pool.

**Layer 5 — TLS profile rotation on hard-limit (May 2026 breakthrough):**
Different TLS profiles have **different trust budgets** at the same IP. When profile A is exhausted, profile B may still have headroom.

```python
EFFECTIVE_LADDER = [
    "chrome145",     # highest trust budget
    "chrome142",
    "chrome146",
    "edge101",
    "safari2601",
]
# Auto-blocked: chrome120, chrome131, chrome136, firefox133, firefox144
```

On 403 / non-JSON body / `tosv.html` response:
1. Re-instantiate fetcher with next profile in ladder
2. Re-run deep primer (markets → search) with fresh fingerprint
3. Retry the **same page** (not page+1) — don't lose data

**Quantified impact:** keyword `"trump"` maxPages=25 went from 4 pages (~40 articles) → 18 pages (169 unique articles). `"tesla"` → 20 pages (197 unique). `SAFE_PAGE_LIMIT` raised 5 → 50.

### Strategy 4: Skyscanner warm-up

Skyscanner's PerimeterX issues `_pxhd` and `__Secure-session_id` only on `.net` (regional shards return 403). Warm-up first:

```python
await session.get("https://www.skyscanner.net/")    # required, populates cookies
# Then POST to /g/search-intent/v1/pricecalendar
```

## Cookies to watch

| Cookie | Role | Notes |
| --- | --- | --- |
| `_px3` | Per-page challenge result | Required for API to accept request |
| `_pxhd` | Daily trust marker | Long-lived, sticky to IP |
| `_pxvid` | Visitor ID | Per-browser, long-lived |
| `pxcts` | Challenge counter | Increments per challenge served |
| `__Secure-session_id` | Skyscanner-specific | Required for conductor calls |

**Cookie jar must share across requests in a session.** Lose one of these → re-challenged.

## Detection: distinguishing PerimeterX from Cloudflare

Both can return 403 from the same URL on different days. To know which is blocking:

```python
def detect_waf(response) -> str | None:
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    
    if "cf-ray" in headers_lower or "cf-mitigated" in headers_lower:
        return "cloudflare"
    
    if any(k in response.cookies for k in ("_px3", "_pxhd", "pxcts")):
        return "perimeterx"
    
    body = response.text.lower()
    if "perimeterx" in body or "human security" in body or "px-captcha" in body:
        return "perimeterx"
    if "cloudflare" in body or "cf_chl_" in body:
        return "cloudflare"
    
    return None
```

## What does NOT work

- ❌ Solving the PX captcha challenge programmatically (sub-1% success rate, expensive)
- ❌ Reusing `_px3` cookies across IPs (cookie binds to IP)
- ❌ Adding `accept-encoding: gzip` manually (breaks Chrome fingerprint)
- ❌ Forcing HTTP/3 (no measured benefit; some PX zones flag h3)
- ❌ `curl_cffi chrome120` against Bloomberg/Zillow (stale, blocklisted)

## Caveats

- **PerimeterX deploys vary wildly between sites.** Bloomberg's `PX8FCGYgk4` config differs from Zillow's `PXcXXXXXXX`. A bypass that works on one may fail on another.
- **Trust budget is per-IP per-profile.** Burning chrome145 on Bloomberg doesn't burn it on Zillow. But within a single run, exhausting it on a site means rotate.
- **PerimeterX has soft 200s.** `tosv.html` body returned with 200 is a "ToS violation" soft block — detect with body markers, treat as 403.
- **Residential proxy quality matters.** Apify Residential trust score varies per country. US/UK have higher baseline; some emerging-market shards trigger PX faster.
- **`requestId: 0` + empty `results: []` on Zillow** is a soft block disguised as success — see [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md) `classify_response()` pattern.

## Where used

- Bloomberg article-scraper (`scrapling safari2601` from datacenter)
- Bloomberg news-search (5-layer evolution, TLS rotation breakthrough)
- Zillow scraper (profile ladder, multi-step warmup, `classify_response()` for soft-block detection)
- Skyscanner (warmup `.net`, sticky session)
- StockX (PerimeterX-flavored Cloudflare, hybrid primp/curl_cffi)

## See also
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`skills/session-pool-rotation.md`](../skills/session-pool-rotation.md)
- [`skills/cookie-warmup.md`](../skills/cookie-warmup.md)
