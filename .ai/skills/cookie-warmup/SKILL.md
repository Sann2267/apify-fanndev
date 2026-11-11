---
name: cookie-warmup
description: "Visit a benign page first to obtain the trust cookie a WAF requires before it serves API responses. Use when an API endpoint returns 403 even with a correct TLS profile, for Akamai (_abck), PerimeterX (_pxhd), DataDome (_dd_s), or Aliyun (aep_usuc_f)."
---

# Cookie Warm-Up Bootstrap

> **Many WAFs (Akamai, PerimeterX, DataDome, Aliyun) issue an "I-trust-you" cookie only when you visit a benign page first.** Hit the API directly and you'll get 403 forever. Visit `/` or a category page first, and the same client receives cookies that unlock the API.

## Problem

Modern bot defense uses a two-phase model:
1. **Visit-time challenge:** First HTML page sets a probationary cookie (`_abck`, `_pxhd`, `_dd_s`, `aep_usuc_f`) plus a JS challenge.
2. **API gate:** Subsequent XHR/fetch calls require those cookies to be present and valid.

If your scraper goes straight to the API endpoint without phase 1, the API returns 403 — even though the API itself isn't doing the blocking.

## Solution: idempotent warm-up before first API call

### Step 1: identify the warm-up URL

The warm-up URL depends on what entity you're about to query:

| Target | Warm-up URL | Why |
| --- | --- | --- |
| Tokopedia API | `https://www.tokopedia.com/` | Akamai cookie jar bootstrap |
| Shopee API | `https://shopee.{country}/` | Region detection cookies (`SPC_F`, `csrftoken`) |
| Airbnb GraphQL | `https://www.airbnb.com/s/{city}/homes` | DataDome cookie + SRP referer chain |
| TripAdvisor GraphQL | `https://www.tripadvisor.com/Hotels-g{geo}-...` | DataDome cookie + JSON-LD seed |
| Skyscanner conductor | `https://www.skyscanner.net/` | PerimeterX `_pxhd` + `__Secure-session_id` |
| Bloomberg article | `https://www.bloomberg.com/search` | PerimeterX visit-time challenge for deep pagination |
| TikTok web | `https://www.tiktok.com/explore` | Cookies + mssdk-sg msToken cache |
| Instagram GraphQL | `https://www.instagram.com/p/<shortcode>/` (entity-specific!) | LSD per-page nonce |
| Facebook GraphQL | `https://www.facebook.com/<page>/` (entity-specific!) | LSD + Comet route bundle |
| Pinterest Resource API | `https://www.pinterest.com/{user}/` | `_pinterest_sess` setup |
| Reddit OAuth | n/a — OAuth flow IS the warm-up | — |
| Alibaba search | `https://www.alibaba.com/` + cookie `aep_usuc_f` (USD/US/en_US) | Region locale priming |
| Google Maps | `https://www.google.com/maps/` (NAVIGATE_HEADERS) | `__Secure-BUCKET`, `__Secure-ENID`, `CONSENT=YES+1` |

### Step 2: idempotent warm-up function

```python
class WarmableSession:
    def __init__(self, session, warmup_url: str, warmup_headers: dict | None = None):
        self.session = session
        self.warmup_url = warmup_url
        self.warmup_headers = warmup_headers or {}
        self._warm = False
    
    async def ensure_warm(self):
        if self._warm:
            return
        r = await self.session.get(self.warmup_url, headers=self.warmup_headers)
        if r.status_code != 200:
            raise RuntimeError(f"Warmup failed: {r.status_code}")
        self._warm = True
    
    async def call_api(self, *args, **kwargs):
        await self.ensure_warm()
        return await self.session.request(*args, **kwargs)
    
    def reset(self):
        """Call after a 403 to force re-warmup on next call."""
        self._warm = False
```

### Step 3: entity-specific warm-up (Meta family)

For IG/FB/Threads, warming the root is NOT enough. The LSD nonce is tied to the route's React component:

```python
# WRONG — works for some queries, fails silently for others
await session.get("https://www.instagram.com/")

# RIGHT — warm the specific entity URL
post_url = f"https://www.instagram.com/p/{shortcode}/"
r = await session.get(post_url)
tokens = harvest_meta_tokens(r.text, dict(r.cookies))   # see warm-page-token-harvest.md
```

### Step 4: locale-specific cookies (Alibaba, Shopee)

For region-gated sites, pre-set the locale cookie before warm-up to skip the auto-redirect dance:

```python
# Alibaba — force USD/US/en_US
session.cookies.set("aep_usuc_f", "site=glo&c_tp=USD&region=US&b_locale=en_US", domain=".alibaba.com")

# Shopee Indonesia — auto-set by visiting region domain
session.cookies.set("SPC_F", "GENERATED_TOKEN", domain=".shopee.co.id")
```

### Step 5: Apify region-routed warm-up

For region-locked content (Shopee SSR, Google Maps reviews), Apify proxy `country_code` aligns IP with the target's locale. This must match the warm-up URL's country domain.

```python
proxy_url = await Actor.create_proxy_configuration(
    groups=["RESIDENTIAL"],
    country_code="ID",          # match shopee.co.id
).new_url()

session = AsyncSession(impersonate="firefox135", proxies={"http": proxy_url, "https": proxy_url})
await session.get("https://shopee.co.id/")
```

## Pattern: NAVIGATE_HEADERS vs BROWSER_HEADERS

Google Maps documents this cleanly — two distinct header sets per request type:

```python
NAVIGATE_HEADERS = {
    # For HTML page loads (warmup)
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

BROWSER_HEADERS = {
    # For AJAX/XHR calls (post-warmup)
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-browser-channel": "stable",
    "x-browser-validation": "<computed>",
    "x-browser-year": "1969",
    "x-maps-diversion-context-bin": "CAE=",
    "referer": "https://www.google.com/maps/",     # critical — referer discipline
}
```

**Always use NAVIGATE for warm-up GETs, BROWSER for subsequent XHRs.** Mixing them is a tell.

## Pattern: referer discipline

The referer header must match what a real browser would send from the warm-up navigation. Wrong referer = silent empty response (not a 403, but a 200 with null data).

| Endpoint | Required referer |
| --- | --- |
| Google Maps `/maps/preview/place` | The place HTML URL, not generic `/maps/` |
| Google Maps `/maps/rpc/photo/listentityphotos` | The specific place URL |
| Tokopedia GraphQL | `https://www.tokopedia.com/` |
| Meta GraphQL | The exact entity URL warmed |
| StockX GraphQL | `https://stockx.com/` |

## Caveats

- **Warmup is idempotent per session, NOT per worker.** Don't re-warm before every call — just on session creation and after a `reset()` due to block detection.
- **Cookie jar must persist between warm-up and API call.** Using a fresh `Session` for each is the most common bug.
- **Warmup response itself can be 403.** That means TLS profile is wrong before cookies even matter — see [`skills/tls-fingerprinting.md`](../tls-fingerprinting/SKILL.md).
- **Apify session_id rotation invalidates warmup.** New egress IP = new cookie jar = warm-up needed again.
- **Some sites issue cookies *only* on the second request** (visit-time challenge has 2 phases — first GET sets challenge, second GET sets trust cookie). For Akamai-heavy targets, do TWO warm-up GETs spaced ~500ms apart.

## Where used

- Tokopedia (homepage GET before GraphQL — `init_session()`)
- Shopee (regional warmup + cookie seeding)
- Bloomberg news-search (primer fetch + sec layer rotation)
- Google Maps suite (NAVIGATE vs BROWSER headers, dual profiles)
- Alibaba suite (`aep_usuc_f` locale priming)
- Skyscanner (warmup `.net` for `_pxhd` + `__Secure-session_id`)
- TikTok (`init_session()` to `/explore`)
- Zillow (multi-step: GET / → sleep 700-1400ms → GET region → JSON API)

## See also
- [`skills/session-pool-rotation.md`](../session-pool-rotation/SKILL.md)
- [`skills/warm-page-token-harvest.md`](../warm-page-token-harvest/SKILL.md)
- [`anti-bot/akamai.md`](../../anti-bot/akamai.md)
- [`anti-bot/perimeterx.md`](../../anti-bot/perimeterx.md)
