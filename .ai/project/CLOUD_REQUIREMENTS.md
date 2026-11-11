# Cloud-run requirements — which actors need Apify + residential proxy

> Reference note: which of the 24 actors return full data from a plain
> local run, and which **must** run on Apify with a RESIDENTIAL proxy
> because the target blocks datacenter/home ASN upstream of TLS.
> Verified 2026-06-06 (after the primp valid-profile fix, see
> [PROBLEMS.md](PROBLEMS.md#primp-stale-profile-names-silently-fall-back-to-random-2026-05-30)).

## TL;DR matrix

| Actor | Local (no proxy) | WAF | Needs cloud + residential? |
|---|---|---|---|
| **StockX** ×5 (search, product, orderbook, sales-history, release-calendar) | ✅ full | Cloudflare (light on these surfaces) | ❌ runs fine local & cloud (DC ok) |
| **Walmart** ×4 (search, product, reviews, seller) | ✅ full | PerimeterX | ⚠️ local often works; **residential recommended** for sustained volume (PX flags repeat DC IPs) |
| **eBay** search + product | ✅ full (post-fix, IP-dependent) | Akamai | ⚠️ works from a warm IP after homepage warmup; **residential for reliability** — Akamai `_abck` binds to IP |
| **Etsy** shop | ⚠️ intermittently full | DataDome | ✅ **residential** — slips through sometimes, not dependable |
| **Etsy** search + product | ❌ 403 local | DataDome | ✅ **residential required** — blocks DC/home ASN before TLS |
| **Alibaba** search, company, rfq, review | ✅ full | Aliyun (light on these) | ❌ local ok; residential helps at volume |
| **Alibaba** product | ❌ WAF local | Aliyun (heavy on PDP) | ✅ **residential required** |
| **AliExpress** ×5 (search, category, product, store, review) | ❌ Baxia WAF local | Aliyun/Baxia | ✅ **residential required** — and product/PDP is CSR-shell even then (see [INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md)) |

## Hard-blocked locally (always need residential on Apify)

These return only a diagnostic/error row from a local datacenter/home IP —
the WAF rejects the ASN before the TLS handshake even matters:

- `alibaba-product-scraper` — Aliyun WAF on the product detail gateway
- `aliexpress-search-scraper`, `aliexpress-category-scraper`,
  `aliexpress-product-scraper`, `aliexpress-store-scraper`,
  `aliexpress-review-scraper` — Baxia/Aliyun (and PDP is CSR-only)
- `etsy-search-scraper`, `etsy-product-scraper` — DataDome

## Works locally, but use residential in production

Pass from a clean local IP, but the WAF will flag a datacenter IP that
hammers it — schedule these with `RESIDENTIAL` proxy for any real volume:

- `etsy-shop-scraper` — DataDome (intermittent local success)
- `ebay-search-scraper`, `ebay-product-scraper` — Akamai (needs homepage
  warmup; `_abck` cookie is IP-bound)
- `walmart-*` ×4 — PerimeterX clears ~attempt 2; residential reduces retries

## Runs anywhere (datacenter proxy or no proxy both fine)

- All 5 `stockx-*`
- `alibaba-search`, `alibaba-company`, `alibaba-rfq`, `alibaba-review`

## Apify proxy config to use

```jsonc
// For the residential-required actors:
"proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
// StockX / Alibaba-light: datacenter is enough
"proxyConfiguration": { "useApifyProxy": true }
```

Note: the primp (no-proxy) transport is only used on local test runs. On
Apify, every actor switches to curl_cffi with the proxy — primp 407s on
Apify proxy URLs (comma in username). See [CRAWLING_METHOD.md](CRAWLING_METHOD.md).
