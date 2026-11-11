---
name: tls-fingerprinting
description: "Pick the right TLS-impersonating HTTP client (curl_cffi, primp, scrapling, impit) to defeat WAF JA3/JA4 fingerprint detection. Use when a scraper gets a 403 or block before any HTML is parsed, when choosing an HTTP library for a new target, or when the site sits behind Cloudflare, DataDome, PerimeterX, Akamai, or Aliyun."
---

# TLS Fingerprinting & HTTP Client Selection

> **The single most important variable in modern scraping.** WAFs (Cloudflare, PerimeterX, DataDome, Akamai, Aliyun) inspect TLS ClientHello — your JA3/JA4 hash and HTTP/2 pseudo-header order — *before* parsing your User-Agent. Plain `requests`/`httpx` defaults are instantly recognizable as Python and get a 403 baseline. The library you pick decides whether you ever see HTML.

## Problem

Default Python HTTP libraries emit a Python-shaped TLS handshake. WAFs maintain blocklists of these fingerprints. Header spoofing alone doesn't help — the JA3 is set in the TCP layer before any HTTP frame is sent.

## Solution: pick the right library for the target

### The 4 libraries in regular rotation

| Library | TLS stack | Strongest against | Notes |
| --- | --- | --- | --- |
| **`curl_cffi`** | curl-impersonate (BoringSSL) | Akamai, Cloudflare (most), Aliyun, generic CDN | Default baseline. Profiles: `chrome120/131/136/142/145/146`, `firefox133/135`, `safari17/18`. |
| **`primp`** | Rust `rquest` (BoringSSL) | DataDome, Cloudflare-when-curl-fails | Rust impl emits JA3 that DataDome hasn't burned. 27-profile shuffle pool viable for WSJ/Barron's. |
| **`scrapling[fetchers]`** | Bundles curl_cffi but adds `safari2601`, `safari260`, `edge101` | PerimeterX (Bloomberg), IBD WordPress REST | The Safari 26.0.1 profile is the key — released after PerimeterX's last fingerprint refresh. |
| **`impit`** | Custom TLS stack | Legacy DataDome, Forbes/Reuters edge cases | Niche fallback. |

### Profile selection cheat sheet

| Target | Library | Profile | Verified |
| --- | --- | --- | --- |
| Cloudflare (Capterra) | `curl_cffi` | `firefox133` ✅ | All Chromium profiles get `cf-mitigated: challenge` 403 |
| Cloudflare (FT) | `curl_cffi` | `chrome145` + UA `Googlebot-News` | Zephr paywall → GRANTED |
| Cloudflare (StockX) | `curl_cffi` / `primp` rotate | `safari17/18_0` | Profile rotation on 403/407/429/503 |
| Cloudflare (Investing.com) | `primp` | random profile | Standard |
| PerimeterX (Bloomberg) | `scrapling` | `safari2601` (fallback `safari260`) | **Critical**: works from Apify datacenter IP, no residential needed |
| PerimeterX (Zillow) | `curl_cffi` | `chrome136 → 142 → 146 → safari260` ladder | `chrome120` blocklisted |
| PerimeterX (Bloomberg deep pagination) | `scrapling` | rotate `chrome145 > chrome142 > chrome146 > edge101 > safari2601` | TLS-profile-rotation-on-403 unlocks 4× more pages |
| PerimeterX (Skyscanner) | `curl_cffi` | `chrome131` | + warm-up GET `skyscanner.net` first |
| DataDome (Reuters/Forbes) | `primp` | `chrome_100`–`chrome_133`, `firefox_109`–`firefox_133`, `safari_15`–`safari_18`, `okhttp_4_9/4_10` | Blocked: `chrome_133_0`, `safari_18_2`, `okhttp_3_9/5` |
| DataDome (WSJ/Barron's) | `primp` | 27-profile shuffle pool | + US Residential proxy |
| DataDome (Airbnb) | `curl_cffi` | `chrome131` | + sticky session, 1 req/sec/IP cap |
| DataDome (TripAdvisor) | `primp` | rquest default | `curl_cffi chrome131` burned by DataDome JA3 |
| Akamai (Tokopedia) | `curl_cffi` | `chrome131` | + homepage GET warmup |
| Aliyun WAF (Alibaba) | `curl_cffi` | `safari18_0 → safari17_0 → chrome131` rotate | + body-marker detection (`baxia-manager`, `punish.html`) |
| Kasada (Realtor.com) | `curl_cffi` | any profile + UA `Googlebot/2.1` | UA is the actual bypass, not TLS |
| TikTok web | `curl_cffi` | `chrome110` | `chrome131` faster rate-limited |
| Meta (IG/FB/Threads) | `curl_cffi` | `chrome131` | + warm-page token harvest |
| Twitter (X) | `curl_cffi` | `chrome131` | + bundle queryId harvest + guest token |
| Reddit | `curl_cffi` | `chrome131` | UA must be **real Chrome 131 string**, not library default |

### What does NOT work

- ❌ Plain `requests` against any major target — instant 403/2146.
- ❌ Plain `httpx` defaults — same fate.
- ❌ Manual UA spoof without TLS impersonation — JA3 leaks Python.
- ❌ `curl_cffi` *Firefox* profiles silently fall back to `random` (curl_cffi only supports Chrome/Safari/Edge real Firefox). For Firefox JA3 use `primp` or `scrapling`.
- ❌ Overriding `Accept-Encoding` manually — real Chrome 131 sends `gzip, deflate, br, zstd`. Override breaks fingerprint. Let the impersonation library set it.
- ❌ Overriding HTTP/2 pseudo-header order — let the library handle.
- ❌ Forcing HTTP/3 / QUIC upgrade — pin h2 (most WAFs don't have h3 fingerprints yet).

## Pattern: profile rotation ladder

```python
from curl_cffi import requests as cc_requests

PROFILES = ["chrome145", "chrome142", "chrome146", "edge101", "safari2601"]

async def fetch_with_rotation(url: str, max_retries: int = len(PROFILES)):
    last_err = None
    for profile in PROFILES:
        try:
            r = cc_requests.get(url, impersonate=profile, timeout=30)
            if r.status_code in (200, 404):
                return r
            if r.status_code in (403, 407, 429, 503):
                # Block — try next profile
                last_err = f"{profile}: HTTP {r.status_code}"
                continue
        except Exception as e:
            last_err = f"{profile}: {e!r}"
            continue
    raise RuntimeError(f"All profiles burned: {last_err}")
```

## Pattern: body-marker block detection (Aliyun, soft blocks)

Some WAFs return **HTTP 200** with a challenge body. Status-code-only detection misses these.

```python
BLOCK_MARKERS = [
    b"_____tmd_____",
    b"baxia-manager",
    b"sufei-punish",
    b"punish.html",
    b"sd/punish",
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
]

def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    body = response.content[:8192]  # only scan head, save bytes
    return any(m in body for m in BLOCK_MARKERS)
```

## Caveats

- **Profile freshness rots.** TLS impersonation libraries chase upstream curl-impersonate releases. Every quarter, re-run a smoke test against your top-10 targets and update the working-profile matrix.
- **`curl_cffi` requires native curl-impersonate binaries.** Docker base `apify/actor-python:3.10+` ships them; on local Windows install needs `curl_cffi[binary]`.
- **`scrapling[fetchers]` includes `curl_cffi`** transitively. Don't list both in `requirements.txt` — version mismatch leads to weird import errors.
- **Profile name format differs between libraries:** `primp` uses `safari_17_5`, `curl_cffi` uses `safari18_0`. Don't copy-paste profile names across libraries.
- **`okhttp_*` profiles** in `primp` are surprisingly effective against DataDome (mobile API endpoints often expect mobile TLS).

## Where used

- Online News 26-actor suite (Cloudflare/DataDome via curl_cffi/primp)
- Bloomberg suite (PerimeterX via scrapling safari2601)
- Real-Estate Zillow (PerimeterX profile ladder)
- Travel suite (Airbnb chrome131 / TripAdvisor primp)
- Capterra B2B (Cloudflare via firefox133)
- StockX (CF via safari rotate)
- Alibaba (Aliyun via safari + body-marker)
- TikTok (chrome110)

## See also
- [`anti-bot/cloudflare.md`](../../anti-bot/cloudflare.md)
- [`anti-bot/perimeterx.md`](../../anti-bot/perimeterx.md)
- [`anti-bot/datadome.md`](../../anti-bot/datadome.md)
- [`playbooks/waf-triage.md`](../../playbooks/waf-triage.md)
