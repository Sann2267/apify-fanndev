# Blibli Flash Sale & Promo Extractor

Track how aggressively sellers on [Blibli](https://www.blibli.com) — one of
Indonesia's largest marketplaces — are cutting prices. Scrapes the live
**Flash Sale**, the full **promo campaign catalogue**, and any product
matching a **minimum discount or promo tag**.

Built for competitive pricing intelligence: which competitors are
discounting hardest, in which categories, under which campaign, and how
fast the discounted stock is actually moving.

No login, no API key, no cookies. HTTP-only — no browser.

## Three modes

Pick one per run with the `mode` input.

### 1. `flashSale` — products in the live Flash Sale

Every product in Blibli's running Flash Sale sessions, with the discount,
both prices, the campaign it belongs to, and **how much of the flash-sale
quota is already claimed** — the closest public proxy for sell-through
speed.

```json
{
  "mode": "flashSale",
  "scheduleScope": "current",
  "flashSaleSort": "biggestDiscount",
  "minDiscountPercent": 50
}
```

A full sweep of both advertised sessions returned **1,404 products across
231 merchants**, discounts ranging 0–96%.

### 2. `promoCampaigns` — the promo campaign catalogue

Every published promo campaign with its landing page, category tree and
exact start/end window. Useful for spotting a competitor's campaign before
it goes live, or catching promos about to expire.

```json
{ "mode": "promoCampaigns", "promoSort": "ending_soon" }
```

440 campaigns were live at the time of writing.

### 3. `discountedProducts` — deep discounts by keyword or category

Sweep any keyword or category for products beating a discount threshold,
optionally restricted to a promo programme. This is the mode for
"who is discounting hardest in *my* category".

```json
{
  "mode": "discountedProducts",
  "searchTerms": ["laptop gaming", "skincare"],
  "categories": ["https://www.blibli.com/c3/memory-card/ME-1000006"],
  "minDiscountPercent": 50,
  "searchSort": "bestSelling"
}
```

`categories` accepts a bare code (`FA-1000099`) or a full Blibli category
URL. `promoFilter` restricts to a Blibli promo programme — `extraPromo`,
`FREE_GIFT`, `COMBO`, `WHOLESALE`, `merchantVoucher`, or a specific
campaign code.

## Output

One row per product (or per campaign in mode 2). Blibli's own fields are
passed through **verbatim** — 30+ upstream fields per product including
`price`, `flashsale`, `merchantCode`, `review`, `inventory`, `location`,
`badge` — so nothing is lost to renaming. Fields this actor adds are
prefixed with `_`:

```json
{
  "_input": "1788195600000-1788281999000",
  "_source": "S1-flashsale-v2",
  "_scrapedAt": "2026-09-01T02:47:21Z",

  "name": "Palmolive Naturals Orchid Body Wash [1 L] - Triple Pack",
  "sku": "COP-60023-00933",
  "merchantName": "Colgate Palmolive Indonesia Flagship Store",

  "_discountPercent": 54,
  "_discountSource": "upstream",
  "_contextualDiscountPercent": 57,
  "_listPrice": 380400,
  "_offerPrice": 174000,
  "_savingAmount": 206400,

  "_quotaClaimedPercent": 90,
  "_quotaStatus": "AVAILABLE",
  "_campaignCode": "CAMP-03285",
  "_isExclusive": true,

  "_scheduleStart": "2026-08-31T17:00:00Z",
  "_scheduleEnd": "2026-09-01T16:59:59Z",
  "_productUrl": "https://www.blibli.com/p/...",
  "_merchantUrl": "https://www.blibli.com/merchant/..."
}
```

Two fields deserve a note:

- **`_contextualDiscountPercent`** is the price after stacking
  payment-method and voucher promos — normally a few points deeper than the
  headline discount, and the better measure of real aggressiveness. Blibli
  only publishes it for some products, so it is nullable.
- **`_discountSource`** tells you whether Blibli published the discount
  (`upstream`) or this actor derived it from the prices (`computed`).
  Blibli omits the field entirely for reductions under 1%, which would
  otherwise leave about half the rows of a full run blank.

## Input reference

| Field | Applies to | Description |
| --- | --- | --- |
| `mode` | all | `flashSale`, `promoCampaigns`, or `discountedProducts` |
| `scheduleScope` | flashSale | `current` (live session) or `all` (every advertised session) |
| `flashSaleSort` | flashSale | `biggestDiscount`, `almostSoldOut`, `mostStockLeft`, `cheapest`, `mostExpensive`, `mostSearched`, `relevance` |
| `promoSort` | promoCampaigns | `ending_soon`, `newest`, `popularity`, `relevance` |
| `searchTerms` | discountedProducts | Keywords to sweep |
| `categories` | flashSale, discountedProducts | Category codes or Blibli category URLs |
| `minDiscountPercent` | flashSale, discountedProducts | Keep only products at or above this discount |
| `promoFilter` | discountedProducts | Restrict to a Blibli promo programme |
| `searchSort` | discountedProducts | `relevance`, `bestSelling`, `cheapest`, `mostExpensive`, `newest` |
| `maxItems` | all | Cap records (**per query** in mode 3). `0` = no limit |
| `proxyConfiguration` | all | Apify Residential + country `ID` recommended |

## Known limits

- **A search query tops out at 800 products.** Blibli's search backend
  refuses to serve past page 20 regardless of page size. Go wider by adding
  more search terms or splitting by category — not by raising `maxItems`.
- **`minDiscountPercent` is applied in two stages.** Blibli's own discount
  facet only accepts 10/25/50/75, so the threshold is snapped down to the
  nearest bucket server-side and the exact figure enforced client-side. The
  result is exact; only the number of requests differs.
- **Flash sale categories change per session.** The category list is
  session-specific; an out-of-season category code simply returns nothing.
- **No absolute stock counts.** Blibli exposes only
  `_quotaClaimedPercent` (share of the flash-sale allocation claimed) and a
  coarse `availabilityStatus`, not units remaining.
- **`maxItems` is per query in `discountedProducts` mode**, not per run —
  three queries with `maxItems: 20` yield 60 rows.

## Pricing

**$1.00 per 1,000 results** — pay-per-event, one event
(`apify-default-dataset-item`), charged per record in the dataset. No
subscription, no minimum.

| What you run | Rows | Cost |
| --- | --- | --- |
| Quick evaluation | 50 | $0.05 |
| Category sweep with a discount filter | ~200 | $0.20 |
| Full flash sale sweep, both sessions | 1,404 | $1.40 |

Store category: **ECOMMERCE** — the actor's output is marketplace product
and promotion data; no secondary category, since a second one only dilutes
search ranking without describing anything the actor does.

<details>
<summary>How this price was set</summary>

Retrieved from the Apify Store (live figures, not estimates):

| Actor | Model | Price |
| --- | --- | --- |
| `datawebot/blibli-scraper` (16 users, 5.0★/3) | pay-per-event | $0.80 / 1k primary event |
| `jupri/blibli` (20 users, 853 runs) | flat | $30 / month |
| `shahidirfan/tokopedia-search-scraper` (157 users) | pay-per-event | $1.00 / 1k |
| `pumpkin_jingo/shopee-scraper-id` | pay-per-event | $3.00 / 1k |
| `easyapi/tokopedia-product-scraper` (148 users) | pay-per-event | $4.99 / 1k |
| `codenest/amazon-deals-scraper` | pay-per-event | $0.50 / 1k |

Measured operating cost for this actor: **$0.009 per 1,000 results**
(from a real platform run: compute + residential proxy + dataset writes).

$1.00 / 1k matches the proven Tokopedia price point in the same
Indonesian-marketplace niche, sits ~25% above the only directly comparable
Blibli pay-per-event actor — a modest premium for flash-sale, quota-
depletion and promo-campaign coverage that neither Blibli competitor
offers — and stays well below the $3–$5 upper band. A 50-row trial costs
$0.05, so evaluating it is effectively free.

</details>

## Reliability

Blibli sits behind **Cloudflare**. The actor clears it HTTP-only with TLS
impersonation plus the `Referer` header Cloudflare's rule requires — no
browser, no CAPTCHA solver. On a block it retries with exponential backoff
while rotating both the TLS fingerprint and (when a proxy is configured)
the egress IP.

Runs never fail silently: a blocked run, an upstream schema change, bad
input, or a genuinely empty result each emit a diagnostic row carrying
`_error` and `_errorDetail`, so a downstream join always sees something.

A short run usually succeeds without a proxy. For long or scheduled runs,
use **Apify Residential proxy with country `ID`**.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the full WAF analysis,
endpoint map, and the field-shape traps found during recon.
