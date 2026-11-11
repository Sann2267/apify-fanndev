# Build Report — 24 e-commerce Apify actors

Consolidated chronological change log. The original two top-level
reports (`REPORT.md` 2026-05-07, `BUILD_REPORT.md` 2026-05-12) have
been merged here and deleted. New findings (2026-05-15 / 2026-05-16)
are folded in.

---

## Phase 1 (2026-05-07) — original Node.js suite

Built 11 actors across 5 platforms (StockX × 2, Walmart × 2, eBay × 2,
Etsy × 3, AliExpress × 2) on top of Crawlee `CheerioCrawler` with
`got-scraping`. Each had a `package.json`, `Dockerfile`,
`.actor/{actor,INPUT_SCHEMA}.json`, `src/{main,fingerprint,parser}.js`,
plus a standalone `test_local.js`.

This phase is now historical — the codebase has since migrated to
Python actors with `apify ~= 2.7`. The Node.js builds were retired.

---

## Phase 2 (2026-05-12) — Python rewrite + 4 new actors

Rewrote every actor in Python using `apify ~= 2.7`. Per-actor template:

```
<actor>/
├── .actor/{actor,INPUT_SCHEMA}.json
├── src/{__init__,__main__,main,parser,fingerprint}.py
├── requirements.txt
├── CRAWLING_METHOD.md
├── README.md
└── test_local.py
```

Hybrid transport: `primp` (no proxy) ↔ `curl_cffi` (with proxy).
WAF detection by body markers, not status only. Diagnostic-error
rows on every input.

### Upgrades

- **walmart-search-scraper**: fixed null prices (parser was reading
  `priceInfo.currentPrice.price` instead of `priceInfo.linePrice`),
  added listPrice/savings/priceRange/fulfillment/badges. PerimeterX
  block detection now catches 200 + thin body without `__NEXT_DATA__`.
- **walmart-product-scraper**: added reviewDistribution,
  reviewAspects, topReviews/topPositiveReview/topNegativeReview,
  variantsMap, fulfillmentOptions, trustBadges.
- **aliexpress-search-scraper**: corrected items path from
  `data.mods.itemList.content` → `data.root.fields.mods.itemList.content`
  (the 2026 canonical nests 2 levels deeper). Added 13 new fields
  including orders (parsed numeric) + ordersRaw, p4pType, storeId/Name/Url,
  freeShipping. Bingbot-UA escape hatch added (allows bypass on
  SEO-indexed pages).
- **aliexpress-product-scraper**: detect empty `runParams = {}` shell
  → fall back to JSON-LD → emit `error: "CSR_SHELL"`. SSR path
  enriched: coupons, wishCount, discountPct, originalPrice, videos,
  fiveStarPct, topRated, full shipping array, per-SKU isAvailable.

### New actors

- **walmart-reviews-scraper** — 1 SUMMARY + N REVIEW rows per product.
  Sort options: relevancy/recency/helpful/rating_desc/rating_asc/pos_neg.
- **walmart-seller-scraper** — marketplace seller storefront crawler.
  Privacy-aware contact/address with `contactVisible`/`addressVisible`
  flags.
- **aliexpress-store-scraper** — storefront identity with 3-stage
  fallback: `_init_data_` → JSON-LD Organization → `<title>`/meta tags.
  Emits CSR_SHELL row when nothing is hydrated.
- **aliexpress-category-scraper** — category-browse crawler. Same
  `_init_data_` parser as search-scraper since legacy
  `/category/<id>/<slug>.html` 302s to the same backend.

---

## Phase 3 (2026-05-13) — MTOP investigation & fixes

User-provided browser-capture (`sample-api.py` + `sample-response-api.json`)
revealed the real MTOP request format:

- `type=originaljsonp` (NOT `originaljson`)
- `callback=mtopjsonp1`, `dataType=originaljsonp`, `jsv=2.5.1`
- API v1.0 confirmed working first
- `ext.foreverRandomToken` = `acs_rt` from `acs_usuc_t` cookie
- Response is JSONP: `mtopjsonp1({...})` — strip wrapper

Response structure (verified):
- `data.result.GLOBAL_DATA.globalData.subject` → title
- `data.result.PRICE.targetSkuPriceInfo.salePriceLocal` (pipe-delimited)
- `data.result.HEADER_IMAGE_PC.imagePathList` → images
- `data.result.PC_RATING.totalValidNum` → review count
- `data.result.SKU.skuProperties` → variant axes
- `data.result.SHOP_CARD_PC.{storeName, sellerPositiveRate, sellerInfo}`

Product geo-redirect fix: `aliexpress.com/item/1005006373553410` →
`aliexpress.us/item/3256806187238658`. Product ID changes; track via
`final_url`.

Category URL fix: `/category/<id>/<slug>.html` (404) →
`/w/wholesale-<slug>.html?postCatIds=<id>&isFromCategory=y&page=<n>`.
Both formats remain accessible; old retained as fallback.

Category parser fallback: when `_init_data_` JSON parse fails on
large pages, regex-find `"itemList":{"content":[` directly and
walk the array.

---

## Phase 4 (2026-05-13 → 2026-05-15) — AliExpress MTOP iteration

5 builds (1.0.12 → 1.0.20) of `aliexpress-product-scraper/mtop.py`
to deliver the MTOP token correctly. Key fixes:

- **Cookie-domain isolation**. `www.aliexpress.com` redirects US IPs
  to `www.aliexpress.us`; cookies get `Domain=.aliexpress.us`;
  `acs.aliexpress.com` (`.aliexpress.com`) never receives them. Fix:
  warm-up in a SEPARATE throw-away session; main MTOP session's first
  request goes directly to `acs.aliexpress.com`.
- **Fresh session per PDP call**. `curl_cffi 0.15.x` merges session
  cookies with explicit `Cookie:` headers inconsistently across
  proxy vs direct TLS. Workaround: new `cf_requests.Session(impersonate=...)`
  for each PDP call.
- **Plant `_m_h5_tk` in `initial_cookies={}`** at session creation,
  before any request. Post-request `cookies.update()` does not
  reliably propagate in curl_cffi 0.15.x.
- **Use server-set token when warm-up sets `_m_h5_tk`**. Otherwise
  the server returns `TOKEN_EMPTY` even when the client-generated
  cookie is correctly signed.

**Outcome**: token delivery works (confirmed by error transition
`TOKEN_EMPTY` → `USER_VALIDATE`). But every signed call still hits
Baxia. Path is structurally blocked HTTP-only.

Removed slow regional-TLD fallback that added 90s per request with
no benefit. Final product-scraper behaviour: emit
`{productId, finalUrl, error: "CSR_SHELL", mtopStatus: "FAILED"}`
when MTOP fails.

---

## Phase 5 (2026-05-15) — Probe 10+ alternative endpoints

Run-id audit: `4uUrlA9vBrP6UsNsE`, `Fb4crueeFZQTLGYtZ`, `YKmorEZtOVoCIIhwa`.

| Endpoint | Outcome |
|---|---|
| `m.aliexpress.com/p/detail/{id}.html` | 404 |
| `m.aliexpress.com/item/{id}.html` | 200 / 59 KB **CSR shell** (`runParams = {}` empty) |
| `mtop.aliexpress.pdp.msite.query` | `USER_VALIDATE` |
| `acs-m.aliexpress.com` (alt gateway) | returns homepage, doesn't route MTOP |
| `portals.aliexpress.com` | login wall |
| `ru.aliexpress.com/item/{id}.html` | 404 |
| `aeglodetailweb/api/v1/product` | 404 |
| `openItemApi/itemDetail.do` | returns Taobao homepage |
| Multi-step Baxia replay (GET challenge URL → retry) | challenge only sets `x5secdata`+`x5sectag`; never `_baxia_sec_cookie_`; retry still `USER_VALIDATE` |

Full report: [INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md).

Also live-dumped `items[0].keys()` from `/w/wholesale-*` and verified
that AliExpress **removed** the `store`, `seller`, `shop` objects
from the listing API. Pre-2026 fields `storeId/storeName/storeUrl/aliMemberId`
are permanently null upstream — removed from output schema and replaced
with `hasStorefront: bool` (the only remaining seller signal:
`trace.utLogMap.if_store_enter`).

---

## Phase 6 (2026-05-16) — shoprenderview discovery + reviews actor

User provided `aliexpress-store-api.py` capture for
`shoprenderview.aliexpress.com/async/execute?componentKey=allitems_choice`.
Empirical probe confirmed:

- **Unsigned** (no MD5 signature)
- **Reliable for page 1** from residential IPs (Baxia challenges
  occasionally on cold IPs; retry succeeds)
- **Page 2+ flaky** — Baxia rate-limit triggers `x5secdata`; rotate
  proxy + warm-up via `/store/{id}` to recover
- **Per-product fields include review aggregates**: `averageStar`,
  `averageStarRate` (positive-feedback %), `feedbacks` (review COUNT
  integer, NOT text), `orders`, `sales`, prices, images, promotions

### New actor: `aliexpress-review-scraper`

- Apify ID `m8Zvt1eoKkrM2b1D8`, build 0.1.4
- Input: store URLs or raw seller IDs
- Output: per-product REVIEW_AGGREGATE row
- Verified output: seller 6000002441 returns 60 rows from 2 pages with
  real ratings (4.6★ / 140 reviews / 1316 orders / $16.20 → $0.99 promo)
- Backoff strategy: cold-call page 1 (no warm-up); retries warm up via
  store landing page; 2–5s sleep between attempts; proxy rotates each attempt

### Probed for per-buyer review TEXT — all dead

- `mtop.aliexpress.review.pc.list/1.0` → `FAIL_SYS_TOKEN_EMPTY`
- `feedback.aliexpress.com/display/productEvaluation.htm` → "System busy" generic error
- `evaluation.aliexpress.com/product/getEvaluationByProductId.htm` → 404
- shoprenderview componentKeys (`reviews`, `productReviews`, `feedback`,
  `storeReviews`) → "component key is invalid" / "system error"

Conclusion: per-buyer review text is unobtainable HTTP-only.

### Cleanup: alibaba-review-scraper

The alibaba MTOP review-list endpoint also got the same fate: the
candidate-discovery loop never finds a working API name in
production. Inputs `maxReviewsPerProduct`, `pageSize`, `country`,
`currency`, `language` were only used by that always-failing MTOP
path → removed from `INPUT_SCHEMA.json` and `main.py`. The actor
now emits AGGREGATE rows only (which is what every successful run
produced anyway). Build 1.0.5.

### Cleanup: aliexpress-product-scraper

Removed the temporary `src/probe.py` (probe mode, served its
purpose during phase 5). Restored `productUrls` as required.
Build 1.0.28.

### Schema validation fix: aliexpress-store-scraper

Build 0.1.1 was rejected by Apify with
`Field schema.properties.country.description is required`. Added
`description` (+ `editor`) to every property in
`.actor/INPUT_SCHEMA.json`.

---

## Final state (2026-05-16)

24 actors deployed. See [SCRAPERS.md](SCRAPERS.md) for the inventory
with status, Apify IDs, and what each returns.

| Platform | Working | Degraded | Blocked |
|---|---|---|---|
| StockX | 5 | 0 | 0 |
| Walmart | 4 | 0 | 0 |
| eBay | 2 | 0 | 0 |
| Etsy | 3 | 0 | 0 |
| Alibaba | 4 | 1 (review: aggregate-only) | 0 |
| AliExpress | 3 (search, category, review) | 2 (store, product: CSR-shell row) | 0 |
| **Total** | **21** | **3** | **0** |

No actor returns silent empty results — every input maps to ≥ 1 row
even on hard WAF block, with a diagnostic `error` field set.
