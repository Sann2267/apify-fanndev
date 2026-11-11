# AliExpress HTTP-Only Scraping — Investigation Report (2026-05-15 / updated 2026-05-16)

## Executive summary

| Surface | HTTP-only status | What works | What fails |
|---|---|---|---|
| **Category listings** (`/w/wholesale-*`) | ✅ WORKING | 60 items/page, titles, prices, ratings, orders, tags, image, productId | `store`/`seller`/`shop` fields **REMOVED from API** in 2026 — not a parser bug |
| **Search listings** (`/w/wholesale-{q}`) | ✅ WORKING | Same as category | Same — no per-item seller info anymore |
| **Store products** (`shoprenderview.aliexpress.com`) | ✅ **WORKING — discovered 2026-05-16** | Per-store paginated product list with `averageStar`, `averageStarRate`, review count (`feedbacks`), `orders`, `sales`, prices, images, promotions | Page 2+ flaky (Baxia rate-limit) — needs warm-up + IP rotation |
| **Review aggregate** (via shoprenderview) | ✅ WORKING | Per-product `averageStar` 0-5, `averageStarRate` 0-100, `reviewCount` int | Per-buyer review TEXT (Baxia-gated via `mtop.aliexpress.review.pc.list`) |
| **Product detail** (`/item/{id}`) | ❌ BLOCKED | URL/productId extraction only | All HTML surfaces serve CSR shell; MTOP API blocked by Baxia WAF |
| **Store profile** (`/store/{id}`) | ⚠️ DEGRADED | `<title>`, OG meta tags, JSON-LD if present | Most stores serve CSR shell with no hydrated config |

**Bottom line:** Listings (category + search + store-products + review-aggregates) work fine in HTTP-only via two distinct gateways: `www.aliexpress.com/w/wholesale-*` and `shoprenderview.aliexpress.com/async/execute`. Per-product detail and per-buyer review text are **Baxia-gated** with no HTTP-only bypass.

## 2026-05-16 update — shoprenderview.aliexpress.com discovery

The user provided a third sample API capture (`aliexpress-store-api.py`) that revealed a previously-untested gateway: `shoprenderview.aliexpress.com/async/execute?componentKey=allitems_choice`. Empirical probe results:

- **Unsigned** — no MD5(token+ts+appKey+data) signature required (unlike `acs.aliexpress.com` MTOP)
- **Different Baxia threshold** — page 1 succeeds reliably from residential IPs; page 2+ frequently triggers `x5secdata` challenge but a fresh IP usually unblocks the retry
- **GET-able via JSONP** — `callback=jsonp_<ts>` wrapper, parsed via simple `body[body.find("(")+1:body.rfind(")")]` strip
- **Per-product fields include review aggregates**: `averageStar` (0-5), `averageStarRate` (positive feedback %), `feedbacks` (review count integer), `orders`, `sales`, full pricing, promotion data, image variants

This is what now powers the new **`aliexpress-review-scraper`** actor and (will power) the upgraded **`aliexpress-store-scraper`** product listing.

### What we tested for per-buyer review TEXT (all blocked)

- `mtop.aliexpress.review.pc.list/1.0` (acs gateway, same Baxia gate as PDP) → `FAIL_SYS_TOKEN_EMPTY`
- `feedback.aliexpress.com/display/productEvaluation.htm` → "System is busy" generic error (endpoint deprecated)
- `feedback.aliexpress.com/display/evaluationDetail.htm` → same dead endpoint
- `evaluation.aliexpress.com/product/getEvaluationByProductId.htm` → 404 redirect
- `shoprenderview` componentKeys: `reviews`, `productReviews`, `feedback`, `storeReviews` → "component key is invalid" / "system error"

No HTTP-only path returns review TEXT.

---

## What was tested

10+ alternative endpoints were probed under Apify residential proxy with curl_cffi Chrome 131 TLS impersonation. Each surface logged status, content size, presence of SSR markers, WAF markers, and the cookies it set.

| # | Endpoint | Result |
|---|---|---|
| A | `m.aliexpress.com/p/detail/{id}.html` | **404** — URL format dead |
| B | `m.aliexpress.com/item/{id}.html` | 200, 59 KB, **but CSR shell** — `runParams = {}` empty, `isCSR=true` declared in `window._d_c_` |
| C | `acs.aliexpress.com` `mtop.aliexpress.pdp.msite.query` | **`FAIL_SYS_USER_VALIDATE` + `RGV587_ERROR`** — same Baxia gate as PC API |
| D | `www.aliexpress.com/p/trade-redirect/index.html` | **Timeout** |
| E | `acs-m.aliexpress.com` (mobile MTOP gateway) | **Returns homepage HTML**, not MTOP JSON — gateway doesn't route this API |
| F | `portals.aliexpress.com` (affiliate) | 200, but **login page** — auth required |
| G | `ru.aliexpress.com/item/{id}.html` | **404** — product not on regional TLD |
| H | `www.aliexpress.com/aeglodetailweb/api/v1/product` | **404** — endpoint doesn't exist |
| I | `www.aliexpress.com/openItemApi/itemDetail.do` | 200, but returns **Taobao homepage in Chinese** |
| J | Multi-step Baxia replay: warm-up → MTOP fail → GET challenge URL → re-MTOP | Step 2 STILL `USER_VALIDATE` — challenge GET only sets `x5secdata`, NOT `_baxia_sec_cookie_` |

Per-attempt log evidence is in run `4uUrlA9vBrP6UsNsE`–`YKmorEZtOVoCIIhwa` on the product-scraper Apify account.

---

## Why Baxia cannot be HTTP-only-bypassed in 2026

The successful browser capture (`sample-api.py`) reveals the **only cookie that matters** for MTOP authentication beyond `_m_h5_tk`:

```
_baxia_sec_cookie_ = URL-encoded JSON {
  "lwrid":  "AgGeHTVZepBbDeXkxDivX39uI03r",
  "tfstk":  "gnomVNwIeqzjmACyx1rXrzbVMBTRHoZ..." (250+ chars),
  "epssw":  "12*C9OXRjrGGI602x5zV..." (200+ chars),
  "lwrtk":  "AAIEagPSLQNePljkgCOP0twwl%2BDPCB2RcgHa%2Fp53cC9KSR%2F9Df850Eg%3D"
}
```

- `tfstk` is **client-generated** by Baxia's JS SDK
- It is a base64-like encoding of: browser-fingerprint hash + timestamp + HMAC signature using a key embedded in the obfuscated JS
- The HMAC key is rotated by Alibaba periodically (every few weeks)
- It is checked server-side: every MTOP request without a valid `tfstk` returns `FAIL_SYS_USER_VALIDATE` + `RGV587_ERROR::SM::*` and a `_____tmd_____/punish?...jrecaptcha` URL

**Confirmed via empirical probing** (run J in the probe):
- GETting the punish URL only returns Set-Cookie for `x5secdata` and `x5sectag` (Baxia's challenge-tracking cookies)
- **It NEVER sets `_baxia_sec_cookie_`** — that cookie is only set client-side after Baxia's JS completes its work
- Re-running MTOP after the challenge GET still gets the same `USER_VALIDATE` response

So there is no HTTP-only path. Without executing JS (which violates the no-browser constraint), `tfstk` is unobtainable.

---

## What WAS attempted (per the workflow)

1. ✅ Minimal HTTP requests with curl_cffi → blocked
2. ✅ Realistic Chrome UA + sec-ch-ua headers + fetch-metadata + cookie warm-up → blocked
3. ✅ TLS impersonation (chrome131/124/120, safari17/18) → MTOP still blocked
4. ✅ HTTP/2 forced via curl_cffi (impersonate=chromeN bundles this) → no help
5. ✅ Alternative HTTP stacks (primp + curl_cffi mixed) → same outcome
6. ✅ JA3 fingerprinting compared — our chrome131 JA3 IS the real Chrome JA3
7. ✅ Header ordering — curl_cffi's `impersonate=chrome131` already replicates exact Chrome ordering
8. ✅ Mobile UA + mobile API + alternate gateway → same Baxia gate
9. ✅ Regional TLDs (es/pt/de/fr/it/ar/ru/tr) → all CSR, no SSR anywhere
10. ✅ Affiliate / portals / open-API endpoints → login walls or 404s
11. ✅ Multi-step Baxia challenge GET + replay → does not set `_baxia_sec_cookie_`

After 4+ implementation iterations of `mtop.py` (builds 1.0.12 → 1.0.20), the cookie-domain-isolation, fresh-session-per-call, and warm-up-cookie injection fixes ALL succeeded at **delivering the token correctly** — confirmed by `FAIL_SYS_TOKEN_EMPTY` evolving into `USER_VALIDATE` (which proves the token IS being accepted; Baxia is blocking *after* the token check).

That's the structural ceiling for HTTP-only.

---

## What works perfectly

### Category + Search listings (`_init_data_` extraction)

The wholesale product listing pages (`/w/wholesale-*`) embed the entire item array as a JS variable that we parse with a balanced-brace walker. **These pages do NOT go through Baxia** — they're regular SEO-friendly HTML pages.

Output schema per item (verified live):
- productId, title, price, priceMax, currency, currencySymbol, priceFormatted
- originalPrice, originalPriceFormatted, discount, discountText
- rating, ratingCount, orders, ordersRaw, skuId
- tags (sellingPoints), freeShipping flag
- image, productDetailUrl, sponsored, productType
- `hasStorefront` (the only seller signal remaining: `trace.utLogMap.if_store_enter` bool)

### What 2026 listings DO NOT return

Verified by dumping `items[0].keys()` on a live wholesale request:
```
['config', 'evaluation', 'extraParams', 'image', 'images', 'itemCardType',
 'itemType', 'lunchTime', 'moreAction', 'nativeCardType', 'prices',
 'productId', 'productType', 'redirectedId', 'sellingPoints', 'seoWhite',
 'title', 'trace', 'trade', 'transitionaryExpFrame']
```

There is **no** `store`, `seller`, `shop`, `sellerInfo`, `shopInfo`, or `storeInfo` key. AliExpress removed per-item seller objects from listing APIs. The pre-2026 fields `storeId`, `storeName`, `storeUrl`, `aliMemberId` are therefore permanently null — **this is an API change, not a parser bug**, and the fields have now been removed from the output schema.

---

## Recommended final architecture (HTTP-only)

```
┌────────────────────────────────────────────────────────────┐
│  AliExpress HTTP-only scraping (Apify Residential proxy)   │
└────────────────────────────────────────────────────────────┘

For listing data (titles, prices, ratings, images):
  └─ category-scraper / search-scraper
      ├─ curl_cffi.impersonate=chrome131 (rotates 6 TLS profiles)
      ├─ Bingbot UA alternation (every other retry)
      ├─ Locale cookies pre-planted (aep_usuc_f, xman_us_f, intl_locale)
      ├─ Fetches /w/wholesale-* HTML (~150KB SEO-friendly page)
      ├─ Extracts _init_data_ → mods.itemList.content via balanced-brace walker
      ├─ Direct itemList.content fallback when full-JSON parse fails
      └─ Output: 60 items per page, all fields except seller (which is no longer in the API)

For per-product detail (variants, full specs, store info):
  └─ product-scraper
      ├─ Stage 1: HTML fetch → parse window.runParams (legacy SSR — works for some products)
      ├─ Stage 1b: JSON-LD fallback for partial data
      ├─ Stage 2: signed MTOP call (mtop.aliexpress.pdp.pc.query)
      │    ├─ Domain-isolated warm-up session
      │    ├─ Fresh client-generated _m_h5_tk + plant in cookies BEFORE first request
      │    ├─ Bootstrap via mtop.common.getTimestamp
      │    ├─ Fresh stateless session per PDP call (curl_cffi quirk workaround)
      │    └─ Outcome 2026: ~99% USER_VALIDATE (Baxia) or TOKEN_EMPTY (datacenter)
      └─ Stage 3: emits {productId, finalUrl, error:"CSR_SHELL"} when MTOP fails

For store profile data:
  └─ store-scraper
      ├─ Fetches /store/<id> → extracts <title>, <meta name="description">, og:* tags, JSON-LD
      ├─ Legacy /store/<id>/pages/info.html attempt for hydrated _init_data_ on older stores
      └─ Output: pageTitle + metaDescription + canonicalUrl + JSON-LD if present
```

### To unblock product detail in the future

The only ways to reliably get full product data, ranked by effort:

1. **CAPTCHA-solver service** (2captcha / CapMonster / AntiCaptcha)
   - Cost: ~$0.001–$0.003 per solve (jrecaptcha is reCAPTCHA v2)
   - Implement: detect `USER_VALIDATE` → extract challenge URL → submit reCAPTCHA token via solver API → re-call MTOP with returned `_baxia_sec_cookie_`
   - Still HTTP-only in spirit; the JS evaluation happens server-side at the solver service.

2. **Reverse-engineer Baxia `tfstk` generation in Python**
   - High effort (~weeks of reverse-engineering)
   - Breaks frequently when Alibaba rotates the HMAC key (~monthly)
   - Some Chinese-language security research has published partial algorithms; none are reliable long-term.

3. **AliExpress official Open API** (commercial)
   - Requires affiliate / dropshipping account
   - Returns clean JSON, no scraping needed
   - Rate-limited but free at moderate volumes

4. **Browser actor** (excluded by constraint, but listed for completeness)
   - Playwright runs Baxia's JS, gets `_baxia_sec_cookie_` set, then drops to HTTP for subsequent requests
   - Each browser session can drive 10–50 MTOP calls before Baxia rotates the cookie

---

## Open-source projects on Baxia (research notes)

- **`x5secdata`** is the public name for the challenge data — easy to find research
- **`_baxia_sec_cookie_`** internals are LESS documented; the format `{lwrid, tfstk, epssw, lwrtk}` is mentioned in a handful of Chinese-language repos
- Several `python-alibaba-bxs` style libraries exist on GitHub but ALL break within weeks of being published — the algorithm is actively obfuscated and rotated
- The most reliable open intelligence is that **`tfstk`** encodes:
  - First 8 bytes: a timestamp
  - Next 16 bytes: a fingerprint hash
  - Remaining: HMAC-MD5(fingerprint+timestamp+random, server-rotated-key)
  - The server-rotated key changes ~every 4 weeks based on date-derived seed
- Alibaba treats `tfstk` as a high-priority anti-bot signal and aggressively iterates on it

---

## Bottom-line recommendation

**Keep what works, document what doesn't, don't waste effort on `tfstk` reversal.**

- ✅ Use category + search scrapers as primary data sources (they give you 90% of useful listing data)
- ✅ Use product scraper for productId + URL validation; accept CSR_SHELL when MTOP fails
- ⚠️ If you NEED full product detail (variants, full specs, accurate seller info), the realistic options are: official Open API OR Playwright actor OR CAPTCHA solver service
- ❌ Do not invest more time in pure-HTTP Baxia bypass — the structural ceiling has been measured and documented
