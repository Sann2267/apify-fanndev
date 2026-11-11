# noon.com Scraper

Extract products, prices, full product detail, seller competition, category
trees and brand filters from **noon.com** — the Middle East's largest online
marketplace — across all seven of its storefronts, in English or Arabic.

---

## Why use this actor

- **No account, no login, no API key.** Paste a keyword, a category, a brand or
  a product link and run it.
- **See every seller on a product, not just the one noon shows you.** One SKU
  routinely has 10+ sellers competing, each with their own price, stock level,
  warranty and delivery promise. That is the data behind any repricing or
  buy-box strategy.
- **Seven countries from one actor.** UAE, Saudi Arabia, Egypt, Kuwait, Qatar,
  Bahrain and Oman — each with its own catalogue, its own prices and its own
  currency, correctly labelled on every row.
- **English or Arabic** product titles and descriptions.
- **noon Minutes included** — the 15-minute grocery catalogue, with pack sizes
  and live discounts, which is a completely separate catalogue from the main
  marketplace.
- **Stable, predictable JSON** ready for spreadsheets, databases, dashboards or
  AI pipelines. Every row is stamped with what produced it and when.
- **Automatic retries, honest failures.** A dead product writes an error row
  instead of silently disappearing from your dataset.

---

## How it works

1. Choose what you want in **mode** — search, a category, a brand, one product,
   a product's sellers, the category tree, the available filters, or noon
   Minutes.
2. Fill in the matching field: keywords, category paths, brand codes, or SKUs
   and product links.
3. Pick your **country** and **language**. This decides the catalogue, the
   prices and the currency.
4. Run it. The actor pages through results, removes repeats, and writes clean
   rows to your dataset as it goes.
5. Export to JSON, CSV or Excel, or read it straight from the API.

No scrapers, browsers, accounts or blocks to babysit.

---

## Input

```json
{
  "mode": "search",
  "searchKeywords": ["iphone"],
  "country": "ae",
  "language": "en",
  "sortBy": "popularity",
  "sortDir": "desc",
  "limitPerPage": 200,
  "maxPages": 10,
  "maxItems": 200
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `search`, `category`, `brand`, `product`, `offers`, `categoryTree`, `facets` or `minutesSearch`. |
| `searchKeywords` | array | Keywords. Used by `search`, `facets` and `minutesSearch`. |
| `categoryPaths` | array | Category path or full noon category link, e.g. `electronics-and-mobiles`. Used by `category`, `categoryTree`, `facets`. |
| `brandCodes` | array | Brand code as it appears in the brand's noon link, e.g. `apple`. Used by `brand`. |
| `productSkus` | array | A noon SKU (`N70211544V`) or a full product link. Used by `product` and `offers`. |
| `targets` | array | Optional. One generic list, routed into whichever field the chosen mode needs — handy when chaining actors. |
| `country` | string | `ae`, `sa`, `eg`, `kw`, `qa`, `bh`, `om`. |
| `language` | string | `en` or `ar`. |
| `maxItems` | integer | Stop after this many rows in total. `0` for no limit. |
| `maxPages` | integer | How deep to page each input. noon stops serving results after page 50. |
| `limitPerPage` | integer | Products per page, up to 200. Higher means far fewer requests. |
| `sortBy` / `sortDir` | string | `popularity`, `price`, `new_arrivals`, `discount`, `rating`, plus `asc` / `desc`. |
| `priceMin` / `priceMax` | integer | Optional price window, in the selected country's currency. |
| `brandFilter` | string | Optional. Narrow search or category results to one brand code. |
| `concurrency` | integer | How many products to fetch at once in `product` and `offers` modes. |
| `proxyConfiguration` | object | Leave off for the seven marketplace modes. **Required (Residential) for `minutesSearch`** when running on Apify. |

### Looking up sellers on a product

```json
{
  "mode": "offers",
  "productSkus": ["N70211544V"],
  "country": "ae",
  "language": "en"
}
```

---

## Output

All samples below are **real, unedited output** from live runs. Long text and
long arrays are truncated with `…` rather than invented.

### `search`, `category`, `brand` — product listings

```json
{
  "_input": "iphone",
  "_source": "S1-mp-catalog",
  "_scrapedAt": "2026-09-22T00:26:13Z",
  "recordType": "PRODUCT",
  "country": "ae",
  "language": "en",
  "locale": "en-ae",
  "currency": "AED",
  "page": 1,
  "productUrl": "https://www.noon.com/uae-en/iphone-17-pro-max-256-gb-esim-only-silver-5g-with-facetime-middle-east-version/N70211544V/p/",
  "listing_nbHits": 1309,
  "listing_nbPages": 27,
  "sku": "N70211544V",
  "sku_config": "N70211544V",
  "catalog_sku": "N70211544V-1",
  "brand": "Apple",
  "name": "iPhone 17 Pro Max 256 GB (eSIM only) Silver 5G With FaceTime - Middle East Version",
  "price": 4899,
  "sale_price": null,
  "plp_specifications": {
    "Screen Size": "6.9 in",
    "RAM Size": "12 GB",
    "Battery Size": "5088 mAh",
    "Secondary Camera Resolution": "18 MP"
  },
  "product_rating": { "best_rating": 4.6, "count": 32200, "value": 4.5 },
  "is_buyable": true,
  "is_bestseller": false,
  "store_name": "IKA_2016",
  "image_url": "https://f.nooncdn.com/p/pzsku/Z4C9C7741BAB2EC64D3F7Z/45/_/1779095234/747f6105-3427-46c3-9636-fc776f031f11.jpg",
  "image_urls": ["https://f.nooncdn.com/p/…747f6105-3427-46c3-9636-fc776f031f11.jpg", "… 3 more"],
  "flags": ["fbn", "quick_atc", "… 2 more"]
}
```

### `offers` — every seller competing on one product

One row per seller. This is the real output for SKU `N70211544V`, which had
**11 sellers**:

```json
{
  "_input": "N70211544V",
  "_source": "S1-mp-catalog",
  "_scrapedAt": "2026-09-22T00:26:15Z",
  "recordType": "OFFER",
  "currency": "AED",
  "offerRank": 1,
  "offerCount": 11,
  "product_sku": "N70211544V",
  "product_title": "iPhone 17 Pro Max 256 GB (eSIM only) Silver 5G With FaceTime - Middle East Version",
  "brand": "Apple",
  "product_rating": { "count": 32200, "value": 4.5 },
  "store_name": "IKA_2016",
  "price": 4899,
  "sale_price": null,
  "stock": 2,
  "is_buyable": true,
  "is_returnable": true,
  "warranty": "1 year seller warranty",
  "estimated_delivery": "Get it <b>Tomorrow</b>",
  "return_policy": {
    "code": "returnable_standard",
    "text": "Easy and Hassle Free Returns",
    "url": "https://www.noon.com/en-ae/return-policy"
  }
}
```

The full set of sellers on that run, cheapest first:

| Rank | Seller | Price (AED) | Stock |
| --- | --- | --- | --- |
| 1 | IKA_2016 | 4899 | 2 |
| 2 | Telemix Telecom L.L.C | 4899 | 3 |
| 3 | Gadget Store | 4899 | 1 |
| 4 | iNeo Electronics | 4899 | 3 |
| 5 | Jacky's Electronics | 4899 | 2 |
| … | … | … | … |
| 9 | noon | 5099 | 3 |
| 10 | Heaven Star Electronics Tr | 4999 | 2 |
| 11 | P A P I T A | 5123.54 | 3 |

### `product` — full product detail

```json
{
  "_input": "N70211544V",
  "_source": "S1-mp-catalog",
  "recordType": "PRODUCT_DETAIL",
  "currency": "AED",
  "productUrl": "https://www.noon.com/uae-en/iphone-17-pro-max-…/N70211544V/p/",
  "offerCount": 11,
  "lowestOfferPrice": 4899,
  "highestOfferPrice": 5123.54,
  "rating": { "count": 32200, "value": 4.5 },
  "sku": "N70211544V",
  "product_title": "iPhone 17 Pro Max 256 GB (eSIM only) Silver 5G With FaceTime - Middle East Version",
  "brand": "Apple",
  "brand_code": "apple",
  "long_description": "The innovative design for iPhone 17 Pro Max delivers exceptional durability, breakthrough battery life and unlocks the extraordinary power of the A19 Pro chip. The 48MP Pro Fusion camera system has the longest iPhone Telephoto ever with 8x zoom, and a Center Stage front camera for smarter group self…",
  "feature_bullets": [
    "Super Retina XDR display Footnote 2 Pro Motion technology Always-On display Dynamic Island",
    "Aluminum Unibody Action button Camera Control for faster access to photo and video tools",
    "… 5 more"
  ],
  "specifications": [
    { "code": "expandable_memory_type", "name": "Memory Type", "value": "No Expandable Memory", "value_code": "no_expandable_memory" },
    "… more"
  ],
  "breadcrumbs": [
    { "code": "", "name": "Home" },
    { "code": "electronics-and-mobiles", "name": "Electronics & Mobiles" },
    "… 3 more"
  ]
}
```

### `categoryTree` — noon's category hierarchy

```json
{
  "_input": "electronics-and-mobiles",
  "_source": "S1-mp-catalog",
  "recordType": "CATEGORY",
  "id_category": 10168,
  "id_category_parent": null,
  "code": "electronics-and-mobiles",
  "name": "Electronics & Mobiles",
  "sort_key": 50000,
  "depth": 0,
  "parent_code": null,
  "child_count": 13
}
```

Each `code` can be fed straight back into `category` mode. The tree runs five
levels deep, e.g.
`electronics-and-mobiles/computers-and-accessories/computers-new/laptops/macbooks`.

### `facets` — the filters and brands available in a category

```json
{
  "_input": "laptop",
  "_source": "S1-mp-catalog",
  "recordType": "FACET",
  "target": "search",
  "nbHits": 1285,
  "facetGroup": "facets",
  "code": "is_fbn",
  "name": "Fulfillment",
  "type": "bool",
  "optionCount": 2,
  "options": [
    { "name": "No", "code": "0", "count": 0 },
    { "name": "Yes", "code": "1", "count": 0 }
  ]
}
```

Useful for market research: the `brand` facet is effectively the list of
everyone competing in a category.

### `minutesSearch` — noon Minutes grocery

```json
{
  "_input": "milk",
  "_source": "S1-instant-catalog",
  "recordType": "INSTANT_PRODUCT",
  "currency": "AED",
  "page": 1,
  "whCode": "W00050759A",
  "nbHits": 836,
  "sku": "VF4DD9D53E29860EEF7B0V-1",
  "title": "Nesquik Chocolate Breakfast Cereal 30G & Almarai Fresh Milk Full Fat 2L Combo",
  "price": 18.4,
  "salePrice": 15.6,
  "discountPercent": 15,
  "isBuyable": true,
  "childItemsDetails": [
    { "sku": "Z2B3CAAC3A860E0DCBD5CZ-1", "title": "Fresh Milk Full Fat 2L", "sizeInfo": "2L", "maxQty": 18 },
    { "sku": "ZD123C2E0FB3ECFDAA7B3Z-1", "title": "Chocolate Breakfast Cereal 30g", "sizeInfo": "30g", "maxQty": 4 }
  ]
}
```

### Fields on every row

| Field | Type | Description |
| --- | --- | --- |
| `_input` | string | The exact keyword, category, brand or SKU that produced this row. |
| `_source` | string | Which catalogue answered: the main marketplace or noon Minutes. |
| `_scrapedAt` | string | UTC timestamp for this row. |
| `recordType` | string | `PRODUCT`, `PRODUCT_DETAIL`, `OFFER`, `CATEGORY`, `FACET`, `INSTANT_PRODUCT` or `ERROR`. |
| `country`, `language`, `locale` | string | Which storefront this row came from. |
| `currency` | string | Currency for every price on the row. |
| `_error`, `_errorDetail` | string | Present only on error rows. |

---

## Notes and limits

- **Review text is not available.** noon publishes an aggregate rating —
  `{"count": 32200, "value": 4.5}` — and this actor returns it on products and
  offers. Individual written reviews are not offered by noon's catalogue, so
  this actor does not claim to return them.
- **There is no keyword-suggestion data.** noon does not publish search volume
  or autocomplete through the catalogue, so no mode pretends to.
- **Result counts are approximate.** noon's own `nbHits` drifts between
  identical requests (the same search reported 1309, 1293, 1323 and 1301 on
  consecutive calls). Treat it as a hint. The number of rows you actually
  receive is the real figure.
- **A nonsense keyword returns unrelated products, not zero results.** noon
  falls back to fuzzy matching, so getting rows back does not by itself prove
  the keyword exists in the catalogue.
- **Paging stops at page 50** on noon's side, whatever `maxPages` says. With
  `limitPerPage: 200` that is still up to ~10,000 products per input. For more
  volume, split the job across several categories, brands or price windows.
- **Some repeats across pages are normal** — noon's ranking shifts while you
  page. The actor removes them, so a run of 4 pages at 200 per page returned
  752 unique products rather than 800.
- **noon Minutes is warehouse-based.** Results reflect one Dubai dark store by
  default. Advanced inputs let you point it at another delivery zone.
- **noon Minutes needs a proxy; the other seven modes do not.** noon serves its
  grocery catalogue only to ordinary consumer connections, so when the actor
  runs on Apify's servers that one mode is refused. Switch on **Residential**
  proxy in the country you want and it works. If you forget, the run tells you
  so in plain language instead of returning an empty dataset.
- **Everything else runs proxy-free.** Search, category, brand, product detail,
  seller offers, category tree and filters all work with the proxy switched
  off — verified on Apify.
