# Amazon ASIN Lookup & Buy Box Monitor

Feed it a list of ASINs, get back product detail, the **Buy Box seller**,
stock, return policy and the full variation family — plus price and Buy Box
**changes since your last run**.

Built for retail arbitrage and dynamic-pricing sellers.

No login, no API key. HTTP-only — no browser.

## Read this before you buy: Amazon withholds the offer block

This is the single most important thing about scraping Amazon product pages
anonymously, and it decides whether this actor fits your use case.

Amazon serves logged-out visitors **two different versions** of a product
page:

| | Full page | Reduced page |
| --- | --- | --- |
| Title, brand, rating, reviews, BSR, images, variations | ✅ | ✅ |
| **Price** | ✅ | ❌ not served |
| **Buy Box seller / seller ID** | ✅ | ❌ not served |
| **Ships from, return policy** | ✅ | ❌ not served |

**Which version you get depends on the IP you request from, not the
product.** From a fixed IP the same ASIN returns the same variant every time
— refetched 6 times across 4 TLS fingerprints, always reduced — which is why
warming a session, reusing cookies, `?th=1&psc=1`, `/gp/offer-listing/` and
the `aod` endpoints all fail to help. None of them change the exit IP.

Rotating to a **fresh proxy session** does. Measured over the same 12 ASINs:

| Configuration | ASINs with Buy Box seller |
| --- | --- |
| Residential proxy, single session | 5/10 |
| Residential proxy + `buyBoxRetries: 2` (default) | **10/10** |

So the actor refetches on a new exit IP when the Buy Box is missing. Only one
ASIN actually needed a retry — once a session lands on a good exit, the rest
of the run inherits it. A retry is only accepted if it carries more than the
response it replaces, so it can never downgrade a good row.

This works well, but it is **not a guarantee**: use a residential proxy, and
still treat the flag below as the source of truth.

**So every row carries `buyBoxDataAvailable`.** When it is `false`, the
seller fields are `null` because *Amazon did not serve them* — not because
Amazon is the seller. Never read a null seller as "sold by Amazon".

```
buyBoxDataAvailable = true   ->  price, seller, returns are real
buyBoxDataAvailable = false  ->  those fields are UNKNOWN, not empty
```

Competing-seller lists and used/refurbished offers are a separate matter:
Amazon's all-offers endpoints return 404 to logged-out clients, so this
actor reports the **Buy Box offer only**. For the full offer list you need
Amazon's SP-API.

## What you get

```json
{
  "asin": "B00XIKPUK4",
  "title": "NAKED Whey 2LB 100% Grass Fed Whey Protein Powder",
  "brand": "Naked Nutrition",
  "price": 62.99,
  "currency": "$",
  "inStock": true,
  "condition": "New",
  "rating": 4.3,
  "reviewCount": 10766,
  "bestSellersRank": 288,
  "bestSellersCategory": "Health & Household",
  "buyBoxDataAvailable": true,
  "buyBoxSellerId": "A2GB0T0Z517LEH",
  "buyBoxSellerName": "Naked Nutrition Inc",
  "buyBoxIsAmazon": false,
  "shipsFrom": "Amazon",
  "returnPolicy": "Non-returnable",
  "parentAsin": "B0CS4S2TWH",
  "variationCount": 19,
  "variationDimensions": ["Size", "Flavor Name"],
  "changeType": "PRICE_DECREASED",
  "previousPrice": 68.99,
  "priceDelta": -6.0,
  "priceDeltaPercent": -8.7
}
```

Field coverage over 10 fetched ASINs:

| Field | Single session | With `buyBoxRetries: 2` |
| --- | --- | --- |
| title, rating, reviewCount, parentAsin | 10/10 | 10/10 |
| bestSellersRank, imageUrl, childAsins | 9/10 | 9/10 |
| brand, featureBullets | 8/10 | 8/10 |
| **price, Buy Box seller** | 5/10 | **10/10** |

Two ASINs were blocked outright in both runs and emitted diagnostic rows.

## Monitoring changes

Set `trackChanges: true` and the actor stores a snapshot in a named
key-value store, then labels every row on the next run:

```
NEW · UNCHANGED · PRICE_INCREASED · PRICE_DECREASED
BUYBOX_SELLER_CHANGED · BACK_IN_STOCK · OUT_OF_STOCK
```

Schedule it and you have a Buy Box watch on your ASIN portfolio.

**A withheld offer block never fires a false alert.** If Amazon served a
seller last run and withheld it this run, that is `UNCHANGED`, not
`BUYBOX_SELLER_CHANGED` — otherwise a bad proxy session would make half your
portfolio alert at once. The same guard applies to stock.

Use different `snapshotName` values to track separate portfolios.

## Input

```json
{
  "asins": ["B00XIKPUK4", "B06XX65GS1", "https://www.amazon.com/dp/B01MQQ4RFA"],
  "marketplace": "com",
  "trackChanges": true,
  "expandVariations": false
}
```

| Field | Description |
| --- | --- |
| `asins` | ASINs to look up. Product URLs work too — the ASIN is extracted |
| `marketplace` | com, co.uk, de, fr, it, es, ca, com.au, co.jp, in |
| `includeVariations` | Capture parent/child ASINs and dimensions (default on) |
| `expandVariations` | Also scrape each child as its own row, for per-variant prices |
| `buyBoxRetries` | Refetches on a fresh proxy IP when the Buy Box is missing (default 2) |
| `maxVariationsPerAsin` | Cap children fetched per product (default 5) |
| `trackChanges` | Compare against the previous run |
| `snapshotName` | Named store for the snapshot — one per portfolio |
| `delaySeconds` | Pacing between products |
| `proxyConfiguration` | Residential **strongly recommended** |

## Things worth knowing

**Prices are pinned to the marketplace currency.** Amazon prices from the
request's geo-IP — an Indonesian exit returned `IDR 336,939.57` for a $19.99
item. The actor sends the cookie that forces the marketplace's currency, so
figures stay comparable wherever the run exits from. `currency` is on every
row regardless, so never assume USD.

**A null price is a null price.** The reduced page still contains dozens of
`a-offscreen` price spans belonging to *related products and other variants*.
Reading the first one gave one $25 protein powder a price of **$2489.00**.
The actor only accepts a price from Amazon's canonical price containers, so
a product whose price was not served reports `null` rather than a plausible
wrong number. For a repricing tool that distinction is the whole ballgame.

**`inStock` is tri-state.** `null` means Amazon served no stock signal —
not "out of stock". A cart button on a reduced page is not counted as proof
of stock, because that button is rendered even when no offer exists.

**Blocked ASINs are reported, never silently dropped.** A bot wall emits a
`CAPTCHA_ESCALATION` row so a short run is never mistaken for a short
catalogue. CAPTCHAs are never solved. Expect some blocking without a
residential proxy — 2 of 12 ASINs were blocked from a home IP in testing.

## Known limits

- **Buy Box coverage depends on proxy quality.** 10/10 measured with
  residential + retries, 5/10 on a single session. Always check
  `buyBoxDataAvailable` rather than assuming.
- **Only the Buy Box offer**, not the full offer list. The all-offers panel
  (`aod`) returns 404 to logged-out clients, so competing-seller counts and
  used/refurbished prices are not obtainable — `condition` reflects the New
  offer shown.
- **No sales estimates or bid data** — no public surface exposes them.
- Variation children are only expanded one level, from the ASINs you supply.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the fingerprint matrix, the
full-vs-reduced page investigation, and every endpoint that was ruled out.
