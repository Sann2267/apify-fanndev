# Aliyun WAF (baxia-manager + sufei-punish)

> **The Alibaba Group's in-house WAF — covers alibaba.com, taobao.com, aliexpress.com, lazada.* family.** The pattern looks like a successful HTTP 200 response with a challenge body, not a 403 — so status-code-only detection misses it. Body-marker detection + locale cookie priming + TLS profile rotation is the working combo.

## Diagnosis

- **Looks like 200 OK** but the body is a challenge page
- Body contains any of: `_____tmd_____`, `baxia-manager`, `sufei-punish`, `punish.html`, `sd/punish`
- Headers may set `EagleEye-TraceId` (Alibaba internal request tracer)
- For MTOP gateway: `_m_h5_tk` cookie NOT set on first request = bootstrap failure

## Bypass strategies

### Strategy 1: body-marker detection (essential)

Status-code detection alone misses Aliyun WAF challenges. **Scan the body**:

```python
ALIYUN_BLOCK_MARKERS = [
    b"_____tmd_____",
    b"baxia-manager",
    b"sufei-punish",
    b"punish.html",
    b"sd/punish",
]

def is_aliyun_blocked(response) -> bool:
    body = response.content[:16384]   # head only
    return any(m in body for m in ALIYUN_BLOCK_MARKERS)


# Driver
r = await session.get(url)
if r.status_code >= 400 or is_aliyun_blocked(r):
    await rotate_profile_and_retry()
```

### Strategy 2: TLS profile triple-rotation

Aliyun's `baxia-manager` issues `_m_h5_tk` cookie only for specific Chrome/Safari TLS fingerprints. Iterate through 3 profiles:

```python
ALIYUN_TLS_PROFILES = ["safari18_0", "safari17_0", "chrome131"]

async def fetch_alibaba(session, url: str):
    for profile in ALIYUN_TLS_PROFILES:
        session.impersonate = profile           # if your wrapper supports mutation
        # OR create fresh session per profile:
        # session = AsyncSession(impersonate=profile, ...)
        
        r = await session.get(url)
        if r.status_code == 200 and not is_aliyun_blocked(r):
            return r
    raise RuntimeError(f"All Aliyun TLS profiles blocked for {url}")
```

### Strategy 3: locale cookie priming

Alibaba auto-redirects you to your geo's locale, which can trigger anti-bot. Pre-set `aep_usuc_f` to skip the redirect:

```python
# Force USD / US / en_US locale upfront
session.cookies.set(
    "aep_usuc_f",
    "site=glo&c_tp=USD&region=US&b_locale=en_US",
    domain=".alibaba.com",
)
```

Without this, the first request follows a 302 to your region's domain, often triggering `baxia-manager` check.

### Strategy 4: referer discipline

Aliyun checks that the referer chain makes sense. For product detail page calls:

```python
headers = {
    "Origin":  "https://www.alibaba.com",
    "Referer": "https://www.alibaba.com/",      # always set
}
```

For RFQ subdomain (`sourcing.alibaba.com`), the WAF is significantly more permissive — no special referer needed.

### Strategy 5: MTOP gateway specifics

The MTOP gateway (`h5api.m.alibaba.com`) has its own quirks:
- Bootstrap `_m_h5_tk` via a throwaway request first
- Sign body with MD5 (see [`skills/mtop-signed-requests.md`](../skills/mtop-signed-requests.md))
- TLS profile triple-rotation applies here too

```python
# First call seeds _m_h5_tk
await session.get("https://h5api.m.alibaba.com/h5/mtop.common.getTimestamp/1.0/")

# Then signed calls work
token = session.cookies.get("_m_h5_tk").split("_")[0]
# ... compute MD5 sign ...
```

## Subdomain risk tiers

| Subdomain | Aliyun aggression | Strategy |
| --- | --- | --- |
| `www.alibaba.com` | High | Full TLS rotation + body-marker + cookie priming |
| `sourcing.alibaba.com` (RFQ) | Low | Single profile, minimal warmup |
| `h5api.m.alibaba.com` (MTOP) | High | TLS rotation + MTOP token bootstrap |
| `www.aliexpress.com` | Medium | Similar to alibaba.com but lighter |
| `world.taobao.com` | High | Full rotation |
| `www.lazada.<tld>` | Varies per country | Test per-region |

## Cookie discipline

| Cookie | Role |
| --- | --- |
| `aep_usuc_f` | Locale preference (pre-set to skip redirect) |
| `_m_h5_tk` | MTOP gateway token (bootstrap-required) |
| `EagleEye-TraceId` | Request tracing (set by server, you echo) |
| `xman_*` | Various session markers |

## What does NOT work

- ❌ Status-code-only detection (Aliyun returns 200 with challenge body)
- ❌ `curl_cffi firefox*` profiles (silently fall back to `random`; Aliyun ignores)
- ❌ `requests` / `httpx` defaults (instant block)
- ❌ Sharing `_m_h5_tk` across IPs (binds to IP)
- ❌ Sending `_m_h5_tk_enc` (server doesn't validate, but presence sometimes triggers extra checks)

## Caveats

- **Aliyun deploys differ per Alibaba subsidiary.** Test bypass per-platform; don't assume Alibaba → AliExpress → Taobao all behave identically.
- **MTOP API names are not publicly documented.** Discovery via 498-combination probing (see `mtop-signed-requests.md`).
- **As of May 2026, the Alibaba review-list MTOP API is no longer accessible** — all 498 combinations return `FAIL_SYS_API_NOT_FOUNDED`. Production scrapers fall back to AGGREGATE-only with `mtopStatus` diagnostic.
- **Apify Residential proxy recommended** for high-volume runs even though datacenter works for sparse runs.
- **Locale cookies impact ALL fields** — pricing, currency, descriptions, MOQ — not just display. Set them deliberately.

## Where used

- Alibaba scraper suite (5 actors — search, product, company, RFQ, reviews)
- Pattern reusable across Taobao / AliExpress / Lazada / Tmall family

## See also
- [`skills/mtop-signed-requests.md`](../skills/mtop-signed-requests.md)
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`skills/cookie-warmup.md`](../skills/cookie-warmup.md)
