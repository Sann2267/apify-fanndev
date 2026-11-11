# Klikindomaret (Indomaret Xpress) Scraper

Scrape **klikindomaret.com** — Indomaret's *Klik Xpress* grocery e-commerce (Indonesia) — over its internal JSON API. No login, no API key. HTTP-only for the heavy lifting, with an automatic browser step only where Cloudflare forces one.

## What it extracts (by `mode`)

| Mode | Records | What you get |
| --- | --- | --- |
| `productSearch` | `PRODUCT` | Product listings by **keyword** and/or **category ID** — name, PLU, price, `finalPrice`, discount %, promo, brand, dimensions, stock/quota, image URLs. Paginated to exhaustion (or `maxItems`). |
| `categoryTree` | `CATEGORY` | The full category hierarchy, flattened — one record per node with a breadcrumb `_categoryPath` and `id` (feed those IDs back into `productSearch`). |
| `promoBanners` | `BANNER`, `PROMO_FILTERS` | Homepage promo banners plus the promo-type / meta-category filter catalogue. |
| `searchSuggestions` | `SUGGESTIONS` | Popular keywords, last-seen/last-search, category recommendations. |
| `stores` | `STORE` | Resolve store code + area + coordinates for one or more district IDs. |

## Input

```jsonc
{
  "mode": "productSearch",
  "searchTerms": ["indomie", "kopi"],   // productSearch
  "categoryIds": ["1059"],              // productSearch (from a categoryTree run)
  "storeCode": "",                       // optional; auto-resolved from districtId
  "districtId": "141100100",             // default: Gambir, Jakarta Pusat
  "districtIds": [],                     // stores mode
  "maxItems": 0,                          // 0 = no cap
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

Everything on Klik Xpress is **store-scoped** (click-and-collect / delivery), so catalog data always resolves against a store. Leave `storeCode` empty and the actor resolves the nearest store from `districtId`.

## Output

Raw-passthrough dataset envelope: every upstream field is kept verbatim; actor-added fields are prefixed `_` (`_input`, `_source`, `_scrapedAt`, plus `recordType`, and in `productSearch` a `_query`/`_queryType` for traceability). Failed or empty runs still emit one diagnostic row with `_error` — downstream joins never see a silently empty dataset.

## How it works (WAF)

The site is a Next.js static-export SPA (Webpack Module Federation micro-frontends). The real runtime API is on **`ap-mc.klikindomaret.com/assets-klikidm{module}/api/get/...`**, protected by two independent gates:

1. **AWS WAF** on every `/api/get/` route — needs an `x-aws-waf-token`. The token's proof-of-work is a `NetworkBandwidth` challenge that a headless **Node + jsdom** solver mints in ~2–3 s (no browser). The token is cached and re-minted before it expires.
2. **Cloudflare managed challenge** on the `search/result` route only (the product listing) — needs a `cf_clearance` cookie that only a real browser earns. **Camoufox** (stealth Firefox) solves it once per run; the cookie is then replayed over `curl_cffi` (Firefox TLS profile) for fast bulk paging. Camoufox is launched **only** for `productSearch`; the other four modes are pure HTTP.

TLS profile: `firefox133` (must match Camoufox's Firefox identity so the clearance cookie replays). On a Cloudflare block the actor re-bootstraps clearance; on an AWS block it re-mints the token; both with exponential backoff.

> `api-klik.klikindomaret.com` (the axios fallback base URL in the bundles) is hard Cloudflare-bot-gated on real routes and is deliberately **not** used.

## Local run

```bash
pip install -r requirements.txt
npm install
python -m camoufox fetch            # once, downloads the stealth Firefox
python test_local.py productSearch  # or: categoryTree | promoBanners | searchSuggestions | stores | token
```

## Known limits

- Product data is store-scoped; different `storeCode`/district can show different assortments, prices, and stock.
- `productSearch` requires the Camoufox step; on Apify give the run enough memory (default 4 GB) for the browser.
- The AWS WAF SDK URL and Cloudflare rules can rotate; if `productSearch` starts failing, re-check the `*.sdk.awswaf.com/.../challenge.js` URL in the homepage HTML (`src/constants.py:AWS_SDK_URL`).
- No login-gated data (cart, checkout, account) — public catalog only.
