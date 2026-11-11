# Blibli Merchant Profile & Inventory Scraper

Map any competitor's storefront on [Blibli](https://www.blibli.com) in one
run: their **full product inventory**, **seller ratings**, **response
speed**, **shipping origin**, follower count, review statistics and active
vouchers.

Paste a store URL — or any product link from that store — and get one flat
profile row plus the catalogue.

No login, no API key. HTTP-only — no browser.

## What you get per competitor

```json
{
  "recordType": "MERCHANT_PROFILE",
  "merchantCode": "COP-60023",
  "merchantName": "Colgate Palmolive Indonesia Flagship Store",
  "isOfficial": true,
  "activationDateIso": "2018-05-11T03:27:00Z",

  "badgeId": "Diamond",
  "badgeRating": 99,
  "respondTimeRating": 5.0,
  "productQualityRating": 5.0,
  "orderFulfillmentRating": 5.0,
  "fastCustomerResponseRating": 100,
  "fastFulfillmentRating": 100,
  "orderCompletedRating": 99,
  "positiveFeedbackRating": 99,

  "province": "DKI Jakarta",
  "pickupPointCity": "Kota Bekasi",
  "pickupPointAddress": "Gudang Blibli.com, Komplek Pergudangan ...",
  "pickupPointLatLong": "-6.2038743,106.9686089",
  "fulfilledByBlibli": true,
  "businessHours": [{ "day": "MONDAY", "openingTime": "00.00", "closingTime": "23.59", "open": true }],

  "totalFollowers": 12427,
  "totalReviews": 68842,
  "averageRating": 4.9,
  "negativeSharePercent": 0.72,
  "reviewTopicCounts": { "QUALITY": 1181, "PRICE": 1006, "SHIPMENT": 935 },

  "productCount": 154,
  "voucherCount": 27,
  "vouchers": [{ "title": "Diskon Rp10.000", "minCriteria": "Min. transaksi Rp100.000", "endDateIso": "..." }]
}
```

Plus one `PRODUCT` record per catalogue item:

```json
{
  "recordType": "PRODUCT",
  "sku": "COP-60023-00892",
  "name": "Colgate Optic White Purple Toothpaste [100 g] x 3 Pcs",
  "salePrice": 88500,
  "listPrice": 169200,
  "discountPercent": 48,
  "rating": 4,
  "reviewCount": 128,
  "soldCount": 2380,
  "storeLocation": "Kota Bekasi",
  "categories": ["Kesehatan & Kecantikan", "Perawatan Gigi & Mulut"]
}
```

## Benchmarking competitors

List several stores and you get a directly comparable row each:

| Store | Badge | Response | Ships from | Followers | Products | Vouchers |
| --- | --- | --- | --- | --- | --- | --- |
| Colgate Palmolive | Diamond | 5.0 | Kota Bekasi | 12,427 | 154 | 27 |
| adidas Sports | Diamond | 5.0 | Kab. Bekasi | 43,161 | 3,112 | 25 |

`respondTimeRating` and `fastCustomerResponseRating` answer "how
responsive is this seller", `pickupPointCity` and `fulfilledByBlibli`
answer "how fast can they deliver to my customers", `reviewTopicCounts`
answers "what do their buyers keep bringing up", and `soldCount` across the
catalogue is the closest public proxy for their actual demand.

## Input

```json
{
  "storeUrls": [
    "https://www.blibli.com/merchant/colgate-palmolive-indonesia-flagship-store/COP-60023",
    "ADS-12698",
    "COP-60023-00933"
  ],
  "includeProducts": true,
  "catalogCoverage": "standard"
}
```

| Field | Description |
| --- | --- |
| `storeUrls` | Store URL, bare store code, or **any product URL/SKU from the store** — the store code is the SKU's prefix |
| `includeProducts` | Emit the catalogue. On by default; turn off for a fast profile-only run |
| `catalogCoverage` | `standard` (one sweep, up to 800) or `deep` (extra sort + price-band sweeps for large stores) |
| `maxProductsPerStore` | Cap per store (0 = no limit) |
| `includeReviewStats` | Add rating histogram + review topic counts. On by default |
| `includeVouchers` | Add active vouchers. On by default |
| `proxyConfiguration` | Apify Residential + country `ID` recommended |

## Known limits

- **Very large catalogues cannot be fully enumerated.** Blibli's search
  serves at most 800 products per query. `deep` coverage adds sort and
  price-band sweeps, reaching **2,271 of 3,112** products on the largest
  store tested. `productCount` on the profile always reports the *true*
  catalogue size, so you can see what fraction a run retrieved.
- **No absolute stock levels.** `soldCount` is the demand signal Blibli
  exposes.
- Badge scores are calculated over a rolling window (`badgeCalculationDays`,
  180 in samples), so they lag very recent performance changes.
- A store code that does not exist is reported as a `STORE_NOT_FOUND` error
  row rather than silently producing an all-zero profile — Blibli returns
  HTTP 200 for made-up codes.

## Reliability

Blibli sits behind **Cloudflare**, and the merchant-profile endpoint
additionally blocks *specific TLS fingerprints* — Chrome profiles get a 403
there while every other endpoint works fine on them. This actor leads with
a fingerprint verified against all five endpoints it uses, and a test
guards that ordering so it cannot regress. On a block it retries with
exponential backoff, rotating both fingerprint and (with a proxy) egress IP.

A failing store never sinks the run: it emits an `ERROR` record with
`_error` and `_errorDetail`, and the remaining stores continue.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the full fingerprint
matrix, the endpoints that looked useful but were not, and the measured
catalogue-partition results.
