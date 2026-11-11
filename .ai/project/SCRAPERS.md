# Scrapers inventory

24 Apify actors across 6 platforms. Status verified 2026-05-16.

## Status legend

- ✅ **Working** — production-ready, full data on golden path
- ⚠️ **Degraded** — partial data, returns diagnostic row when full data is unreachable
- ❌ **Blocked** — fundamental anti-bot block, only error row is returned

## StockX (5 actors, all working)

| Actor | Apify ID | Status | Returns |
|---|---|---|---|
| stockx-search-scraper | — | ✅ | Keyword/category search; per-tile ask/bid |
| stockx-product-scraper | — | ✅ | Full product snapshot — market state, statistics, traits, media |
| stockx-orderbook-scraper | — | ✅ | Per-size orderbook: lowest ask, highest bid, spread, 72h velocity |
| stockx-sales-history-scraper | — | ✅ | Annual/90-day/72h sales statistics + per-size 72h activity |
| stockx-release-calendar-scraper | — | ✅ | Upcoming drops with pre-release bid/ask signals (7 categories) |

## Alibaba (5 actors)

| Actor | Apify ID | Status | Returns |
|---|---|---|---|
| alibaba-search-scraper | — | ✅ | Keyword search; full supplier + pricing + trust per card |
| alibaba-product-scraper | — | ✅ | Ladder pricing, SKU matrix, per-SKU inventory, supplier profile |
| alibaba-company-scraper | — | ✅ | Full supplier profile from any Alibaba subdomain |
| alibaba-rfq-scraper | — | ✅ | Live buying requests from the RFQ marketplace |
| alibaba-review-scraper | `DLyfCiK7f0X1POM3P` | ⚠️ | **AGGREGATE only** (averageStar, totalReviewCount, supplierRatingByCriterion). Per-buyer review text is gated by an MTOP endpoint Alibaba no longer exposes publicly. MTOP discovery path was removed in build 1.0.5 — inputs `maxReviewsPerProduct`, `pageSize`, `country`, `currency`, `language` removed as a consequence. |

## AliExpress (5 actors — see [PROBLEMS.md](PROBLEMS.md#baxia-waf-aliexpress))

| Actor | Apify ID | Status | Returns |
|---|---|---|---|
| aliexpress-search-scraper | `plAVI5gBE5juyabde` | ✅ | 60 items/page (wholesale search). `_init_data_` JSON walker. **NO** per-item seller fields — AliExpress removed them from the listing API in 2026. |
| aliexpress-category-scraper | `qfCL7MbarZFsm7MvM` | ✅ | 60 items/page (wholesale browse). Same data shape as search. |
| aliexpress-review-scraper | `m8Zvt1eoKkrM2b1D8` | ✅ | **NEW 2026-05-16**. Per-product review aggregate via `shoprenderview.aliexpress.com`: averageStar, averageStarRate (positive-feedback %), reviewCount (integer), orders, sales text, prices. Per-store paginated. |
| aliexpress-store-scraper | `AszDxwU17tHnoYyDO` | ⚠️ | Storefront identity from CSR-shell `<title>` + meta + JSON-LD. The shoprenderview gateway gives products listing but is currently used in the review-scraper instead. |
| aliexpress-product-scraper | `usPtOtqQzL1d6VoJ7` | ⚠️ | Product ID + finalUrl + `error: "CSR_SHELL"`. **Full product graph is Baxia-blocked HTTP-only.** MTOP returns `FAIL_SYS_USER_VALIDATE`+`RGV587_ERROR` for residential proxy IPs and `FAIL_SYS_TOKEN_EMPTY` for Apify datacenter IPs. |

## Walmart (4 actors, all working)

| Actor | Apify ID | Status | Returns |
|---|---|---|---|
| walmart-search-scraper | — | ✅ | 60 items/page; full pricing, fulfillment, badges, ratings |
| walmart-product-scraper | — | ✅ | Full product graph + reviewDistribution + reviewAspects + topReviews + variants |
| walmart-reviews-scraper | — | ✅ | 1 SUMMARY row + paginated REVIEW rows per product; recommendedPercentage, AI summaries |
| walmart-seller-scraper | — | ✅ | Marketplace seller profile: identity, trust, branding, contact (privacy-aware), ratings |

## eBay (2 actors, all working)

| Actor | Status | Returns |
|---|---|---|
| ebay-search-scraper | ✅ | Search results with auction state |
| ebay-product-scraper | ✅ | Product graph + seller, shipping, return policy |

## Etsy (3 actors, all working)

| Actor | Status | Returns |
|---|---|---|
| etsy-search-scraper | ✅ | Listing results with seller signals |
| etsy-product-scraper | ✅ | Listing graph + variations + reviews + shop |
| etsy-shop-scraper | ✅ | Shop profile + listings sample |

## Per-actor file layout

```
<actor>/
├── .actor/
│   ├── actor.json          # Apify manifest
│   └── INPUT_SCHEMA.json   # Apify input schema (Apify enforces description on every property)
├── src/
│   ├── __init__.py
│   ├── __main__.py         # `python -m src` entry
│   ├── fingerprint.py      # primp + curl_cffi clients with locale cookies
│   ├── main.py             # asyncio Actor entry
│   └── parser.py           # site-specific extraction
├── CRAWLING_METHOD.md      # per-actor reverse-engineering notes (human/marketplace)
├── README.md               # marketplace listing
├── requirements.txt
└── test_local.py           # standalone runner — what `qa_actors.py` calls
```
