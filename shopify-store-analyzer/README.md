# Shopify Store Analyzer

Paste a Shopify store URL and get back who they are, which theme they run, their full product catalogue with prices and variants, what they added recently — and what changed since your last run.

## Why use this actor

- **No account, no login, no API key.** It reads only what the store publishes openly.
- **One URL is all you need.** No store IDs, no handles, no configuration.
- **Complete pricing data** — every variant with its price, compare-at price, SKU, weight, option values and live availability.
- **Theme detection** — which theme the store runs (Dawn, Split, Horizon…), its version, and whether it is an official Shopify Theme Store theme or a custom build.
- **New product discovery** — everything published in the last N days, found without reading the whole catalogue.
- **Change tracking** — run it on a schedule and get new, removed, price-changed and back-in-stock products between runs.
- **Works on custom-built storefronts too.** Many large brands run a custom front end; the actor still finds their catalogue.
- **Stable JSON output** with one consistent envelope on every row, ready for a spreadsheet, database or pipeline.

## How it works

1. You give it one or more store URLs — a bare domain like `allbirds.com` is fine.
2. It identifies the store, reads its public shop profile and works out which theme powers the storefront.
3. It reads the product catalogue, page by page, including every variant and price.
4. Results stream into your dataset as flat JSON rows, ready to download as JSON, CSV or Excel.

You do not need to manage scrapers, browsers, accounts or store credentials.

## Modes

| Mode | Reads | Returns |
|---|---|---|
| `store-analysis` *(default)* | Store URLs | Store profile, theme, catalogue statistics + the newest products |
| `products` | Store URLs | The full catalogue, one row per product (optionally per variant) |
| `new-products` | Store URLs | Only products published in the last N days |
| `changes` | Store URLs | New / removed / price / stock changes since your previous run |
| `collections` | Store URLs | Every collection with its product count |
| `detect` | Store URLs | Just "is this Shopify, and which theme" — fast and cheap for qualifying many domains |

## Input

```json
{
  "mode": "store-analysis",
  "storeUrls": ["https://allbirds.com", "colourpop.com", "brooklinen.com"],
  "maxProducts": 1000,
  "newWithinDays": 7,
  "newestProducts": 10,
  "explodeVariants": false,
  "maxConcurrency": 4
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | Which of the six modes to run. Default `store-analysis`. |
| `storeUrls` | array | One or more store URLs or bare domains. A `myshopify.com` address works too. |
| `maxProducts` | integer | Cap on products read per store. `0` or empty means the whole catalogue. Default 1000. |
| `newWithinDays` | integer | `new-products` mode — how far back counts as new. Default 7. |
| `newestProducts` | integer | `store-analysis` mode — how many of the most recent products to include. Default 10. |
| `explodeVariants` | boolean | `products` mode — also emit one flat row per variant, for spreadsheets. Default `false`. |
| `maxConcurrency` | integer | How many stores to analyse at once. Default 4. |
| `proxyConfiguration` | object | Optional — not needed, see **Notes and limits**. |

## Output

### `STORE` — the store profile

```json
{
  "_input": "allbirds.com",
  "recordType": "STORE",
  "requestedDomain": "allbirds.com",
  "resolvedDomain": "www.allbirds.com",
  "catalogueDomain": "www.allbirds.com",
  "myshopifyDomain": "weareallbirds.myshopify.com",
  "isShopify": true,
  "detectionConfidence": "confirmed",
  "poweredBy": "Shopify",
  "storefrontType": "liquid-theme",
  "themeName": "allbirds-theme",
  "themeLabel": "[DNAM Theme July 2026]",
  "themeId": 130450260048,
  "themeStoreId": null,
  "themeSchemaVersion": "1.231.12",
  "isThemeStoreTheme": false,
  "shop_id": 11044168,
  "shop_name": "Allbirds",
  "shop_city": "Beverly Hills",
  "shop_province": "California",
  "shop_country": "US",
  "shop_currency": "USD",
  "shop_money_format": "${{amount}}",
  "shop_published_products_count": 294,
  "shop_published_collections_count": 1346,
  "productsScraped": 294,
  "variantCount": 2857,
  "vendorCount": 2,
  "productTypeCount": 5,
  "distinctTagCount": 648,
  "productsOnSale": 1,
  "productsInStock": 104,
  "productsOutOfStock": 190,
  "minPrice": 0.8,
  "maxPrice": 160.0,
  "avgPrice": 93.75,
  "newestPublishedAt": "2026-09-02T11:33:11-07:00"
}
```

| Field | Type | Description |
|---|---|---|
| `isShopify` / `detectionConfidence` | boolean / string | Whether the site is a Shopify store, and how certain. |
| `storefrontType` | string | `liquid-theme` for a standard Shopify theme, `headless` for a custom-built front end. |
| `themeName` | string | The theme powering the store. Empty for custom front ends, which have no theme. |
| `isThemeStoreTheme` | boolean | `true` for an official Shopify Theme Store theme, `false` for a custom or modified one. |
| `shop_*` | mixed | The store's own published profile: name, location, currency, catalogue counts. |
| `productsScraped` vs `shop_published_products_count` | integer | What this run read, versus what the store says it publishes — compare the two to confirm a complete crawl. |
| `avgPrice`, `productsOnSale`, `productsInStock` | number | Catalogue-level pricing and stock summary. |

### `PRODUCT` / `NEW_PRODUCT` — catalogue rows

```json
{
  "_input": "allbirds.com",
  "recordType": "NEW_PRODUCT",
  "storeDomain": "allbirds.com",
  "productUrl": "https://www.allbirds.com/products/free-returns-coverage",
  "id": 7369944137808,
  "title": "Free Returns Coverage",
  "handle": "free-returns-coverage",
  "vendor": "re:do",
  "product_type": "return,package_protection",
  "published_at": "2026-09-02T11:33:11-07:00",
  "created_at": "2026-06-05T07:14:57-07:00",
  "updated_at": "2026-09-15T10:59:44-07:00",
  "tags": ["ATTV_GLOBAL_EXCLUSION_TAG", "exclude_rebuy", "… 3 more"],
  "variantCount": 2,
  "availableVariantCount": 2,
  "inStock": true,
  "minPrice": 0.8,
  "maxPrice": 2.98,
  "maxCompareAtPrice": 2.98,
  "onSale": false,
  "variants": [
    {
      "id": 42436493115472,
      "title": "$0.80",
      "option1": "$0.80",
      "sku": "x-redo",
      "price": "0.80",
      "compare_at_price": "0.80",
      "available": true,
      "grams": 0,
      "position": 1
    },
    { "…": "1 more variant" }
  ],
  "options": [{ "name": "Price", "position": 1, "values": ["$0.80", "$2.98"] }],
  "images": [
    { "id": 36767541592144, "src": "https://cdn.shopify.com/s/files/1/1104/4168/files/Screenshot_2026-06-11_at_10.12.01_AM.png?v=1781197934", "width": 322, "height": 262 }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `title`, `handle`, `vendor`, `product_type`, `tags` | string / array | The product as the store describes it. |
| `published_at` | string | When the product went live — this is what "newly added" is based on. |
| `created_at` | string | When the record was first created, often much earlier than the publish date. |
| `variants` | array | Every variant: price, compare-at price, SKU, availability, option values, weight. |
| `options` | array | The option axes (Size, Colour…) and their values. |
| `images` | array | Product images with source URL and dimensions. |
| `minPrice` / `maxPrice` / `maxCompareAtPrice` | number | Added by this actor — prices as **numbers**, ready to sort and chart (the store publishes them as text). |
| `onSale` / `inStock` / `availableVariantCount` | boolean / integer | Added by this actor — quick flags computed across the variants. |
| `productUrl` | string | Added by this actor — the shoppable link. |

### `VARIANT` — one flat row per variant (`explodeVariants: true`)

```json
{
  "recordType": "VARIANT",
  "storeDomain": "brooklinen.com",
  "productTitle": "Super-Plush Turkish Cotton Hand Towels Set of 2 - Last Call",
  "productHandle": "super-plush-hand-towels-last-call",
  "productType": "Towels",
  "vendor": "Brooklinen",
  "productUrl": "https://www.brooklinen.com/products/super-plush-hand-towels-last-call",
  "id": 42950127452250,
  "title": "Aloe",
  "option1": "Aloe",
  "sku": "HT-103P",
  "priceValue": 33.0,
  "compareAtPriceValue": 55.0,
  "requires_shipping": true,
  "taxable": true
}
```

### `CHANGE` — what moved since your last run

```json
{
  "recordType": "CHANGE",
  "storeDomain": "gymshark.com",
  "changeType": "PRICE_CHANGED",
  "title": "Gymshark Woven Shorts - Indigo Purple",
  "handle": "gymshark-woven-shorts-shorts-purple-ss26",
  "productId": 6806950150346,
  "vendor": "Gymshark | Be a visionary.",
  "product_type": "Womens>Apparel>Shorts>loose",
  "priceBefore": 34.0,
  "priceAfter": 13.6,
  "priceDelta": -20.4
}
```

`changeType` is one of `NEW`, `REMOVED`, `PRICE_CHANGED`, `BACK_IN_STOCK` or `OUT_OF_STOCK`. Each run also emits one `CHANGE_SUMMARY` row with `changesDetected`, `previousCapturedAt` and the product counts on both sides.

The very first run for a store has nothing to compare against, so it stores a baseline and emits a `SNAPSHOT_BASELINE` row marked `first_run_no_baseline` — rather than reporting the entire catalogue as "new". Schedule the actor and the second run onwards will report real changes.

### `COLLECTION`

```json
{
  "recordType": "COLLECTION",
  "storeDomain": "brooklinen.com",
  "collectionUrl": "https://www.brooklinen.com/collections/bath-1",
  "id": 277661352026,
  "title": "All Bath",
  "handle": "bath-1",
  "published_at": "2024-10-09T11:31:47-04:00",
  "updated_at": "2026-09-15T07:02:28-04:00",
  "products_count": 33
}
```

### Error rows

Every URL produces a row, even when it cannot be analysed:

```json
{
  "_input": "nike.com",
  "recordType": "ERROR",
  "_error": "not_shopify",
  "_errorDetail": "nike.com shows no Shopify signals (powered-by='', body markers=0)."
}
```

| `_error` | Meaning |
|---|---|
| `not_shopify` | The site loaded fine but is not a Shopify store. |
| `domain_unreachable` | Nothing loaded — a dead domain, a typo, or the site refused us. Deliberately distinct from `not_shopify`, so a dead domain is never mistaken for a non-Shopify one. |
| `no_public_catalogue` | A Shopify store with a custom front end whose catalogue is not published openly. |
| `bad_input` | The value was not a usable URL. |

Filter on `recordType == "ERROR"` to review which inputs failed and why.

## Notes and limits

- **Product order.** The catalogue is served newest-published-first, which is how `new-products` finds recent arrivals without reading the whole catalogue. On a large store that is the difference between a handful of requests and thousands.
- **`published_at` vs `created_at`.** "New" means **published** — when the product went live in the store. A product can be created months earlier and published today; sorting by `created_at` would miss it.
- **Custom-built storefronts.** Brands running a custom front end still usually publish their catalogue, and the actor finds it — the `catalogueDomain` field tells you where the data came from. A minority publish nothing at all; those return `no_public_catalogue` rather than a half-empty row.
- **Regional storefronts.** Some brands redirect to a country-specific store, which can have a different catalogue and currency. When that happens `resolvedDomain` differs from `requestedDomain` and a note is added, so you always know which storefront the numbers describe. Use a country-specific proxy if you need a particular region.
- **`maxProducts`.** Large stores hold thousands of products (one in our testing reports nearly 10,000). The default caps each store at 1000; set it to `0` for everything.
- **Prices are text upstream.** The store publishes prices as strings; this actor adds numeric `minPrice` / `maxPrice` / `priceValue` fields so you can sort and chart without converting.
- **Proxy is optional.** The default is no proxy and that works. Add one only to pin a region-specific storefront — a proxy will not unlock a store that rate-limits automated traffic, which we tested and confirmed.
- **A few stores rate-limit heavy traffic.** When that happens you get `domain_unreachable` after several retries rather than a wrong answer. The same store can succeed from one network and rate-limit from another, so these error rows describe what this run saw, not a permanent verdict on the store.
