# Blibli Drop-shipper Data Sync

Keep your reseller catalogue accurate. Give it the Blibli SKUs you sell and
it returns the **current price, availability, stock and description** — plus
**exactly what changed since the last run**, so you push updates instead of
re-importing everything.

Built for dropshippers reselling Blibli stock on their own store, Shopee,
Tokopedia, TikTok Shop or a webshop.

No login, no API key. HTTP-only — no browser.

## What it's actually for

Run it on a schedule. Each run tells you, per SKU:

| `changeType` | What you do in your store |
| --- | --- |
| `PRICE_INCREASED` / `PRICE_DECREASED` | Reprice — `changes.price` has from/to and `deltaPercent` |
| `OUT_OF_STOCK` | Pause or hide the listing |
| `BACK_IN_STOCK` | Re-activate it |
| `NAME_CHANGED` | Update your title |
| `BECAME_UNAVAILABLE` | The listing is gone — unpublish |
| `NEW` | First time seen |
| `UNCHANGED` | Nothing to do |

Set `onlyChangedItems: true` and the dataset contains **only the rows you
need to act on** — often a handful out of hundreds.

```json
{
  "sku": "BLL-70058-00122",
  "syncStatus": "OK",
  "name": "SanDisk Ultra microSDXC 64GB C10 UHS-I Card 100MB/s",
  "price": 255000,
  "listPrice": 299000,
  "discountPercent": 15,
  "inStock": true,
  "stockQuantity": 96,
  "changeType": ["PRICE_DECREASED"],
  "changes": { "price": { "from": 299000, "to": 255000, "deltaPercent": -14.72 } },
  "hasChanged": true
}
```

## Input

```json
{
  "productUrls": ["BLL-70058-00122", "COP-60023-00933"],
  "detailedMode": false,
  "trackChanges": true,
  "onlyChangedItems": true
}
```

`productUrls` takes bare SKUs or full product URLs — mix freely. You only
need to store SKUs; the actor reaches any product from its SKU alone.

| Field | Description |
| --- | --- |
| `detailedMode` | Off: bulk lookup, **1 request per 50 SKUs**, gives price + in-stock boolean. On: opens each product page for **exact stock quantity**, description, warranty, categories and all images — 1 request per SKU |
| `verifyMissing` | Re-check missing SKUs on their product page before calling them gone. **Leave this on** — see below |
| `trackChanges` | Compare against the previous run and label each SKU |
| `onlyChangedItems` | Emit only rows that changed |
| `stateStoreName` | Named store holding the snapshot; use one per catalogue |
| `proxyConfiguration` | Residential + country `ID` recommended for scheduled syncs |

## Why `verifyMissing` matters

Blibli's bulk endpoint **silently omits some products that are perfectly
alive.** Verified during recon: SKU `VAM-43292-00654` returns nothing from
the bulk endpoint while its product page shows a buyable listing with stock
6, and search reports it as `AVAILABLE`.

If the actor treated "missing from bulk" as "delisted", it would tell you to
unpublish products that are still selling. So every missing SKU is
re-checked against its product page before being reported as `NOT_FOUND`.
If you switch verification off for speed, those rows say explicitly in
`_errorDetail` that the absence was **not** confirmed.

## Suggested setup

- **Price/stock sync, 2–4× daily**: `detailedMode: false`,
  `onlyChangedItems: true`. A 500-SKU catalogue is ~10 requests.
- **Full content refresh, weekly**: `detailedMode: true`,
  `onlyChangedItems: false` — pulls descriptions, warranty and stock levels
  for rewriting listings.

## Known limits

- **Fast mode gives an in-stock boolean, not a quantity.** Exact stock needs
  `detailedMode`, at one request per SKU.
- **Variants are flagged but not enumerated** — `hasVariants` tells you a
  listing has options, but price and stock describe the default variant.
- A run is a point-in-time snapshot; freshness is whatever your schedule is.
- Descriptions are in Indonesian, as Blibli publishes them.

## Reliability

Blibli sits behind Cloudflare. The actor clears it HTTP-only with TLS
impersonation plus the required `Referer`, retrying with exponential backoff
and rotating both fingerprint and (with a proxy) egress IP on a block. A
failing SKU never sinks the run — it becomes a row with `_error` and
`_errorDetail` while the rest continue.

SKUs absent from a given run are carried forward in the snapshot rather than
dropped, so syncing part of your catalogue does not erase the rest of its
change history.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the endpoint evidence, the
field-by-field comparison of the two modes, and the silent-omission finding.
