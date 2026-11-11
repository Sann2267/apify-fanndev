# Crawling method — Blibli merchant profiles

Recon date: **2026-09-01**. Every figure below was measured live.

## The headline finding: a per-fingerprint WAF rule

Blibli is behind Cloudflare, and as with the sibling actors a `Referer`
header is mandatory. But the merchant-profile endpoint carries an
**additional, fingerprint-specific block** that the other Blibli endpoints
do not:

| TLS profile | `/backend/search/merchant/{code}/info` | every other endpoint used here |
| --- | --- | --- |
| `chrome124` | **403** (248 KB Cloudflare HTML) | 200 |
| `chrome131` | **403** | 200 |
| `safari17_0` | **200** | 200 |
| `safari18_0` | **200** | 200 |
| `firefox133` | **200** | 200 |
| `edge101` | **200** | 200 |
| `chrome99_android` | **200** | 200 |

This is not a blanket `/backend/search/*` block: `/backend/search/products`
and the sibling `/backend/search/brand/{name}/info` both return 200 on
`chrome124`. It is a rule aimed at the merchant-profile path.

Two things follow, and both are load-bearing:

1. **The TLS ladder for this actor must lead with a non-Chrome profile**
   (`safari17_0`, verified against all five endpoints). Leading with
   `chrome124` — the sensible default, and what the other two Blibli actors
   use — would silently lose the entire profile record while every other
   call kept succeeding. A test guards the ladder order.
2. Header tweaking is a dead end here. `Referer` variants, `x-b3-traceid`,
   `channelId`, POST instead of GET, and the slug-instead-of-code form were
   all tried; every one still 403s on `chrome124`. Only the fingerprint
   matters. This is the "one profile failing is a data point, not a
   verdict — run the full ladder" rule earning its keep.

## Endpoints

Found by walking the catalog module bundle
(`catalog/static/<ver>/desktop/index.js` → `js/config.<hash>.js`), which
carries the API map. Those chunk paths are version-hashed and will rotate;
they are recon artifacts only and the actor never fetches them.

| Purpose | Endpoint |
| --- | --- |
| Store profile | `GET /backend/search/merchant/{code}/info` |
| Follower count | `GET /backend/official/merchant-favorites/{code}` |
| Catalogue | `GET /backend/search/products?merchant={code}` |
| Review stats | `GET /backend/product-review/public-reviews?merchantCode={code}` |
| Vouchers | `GET /backend/search/vouchers?merchantCode={code}` |

Note the inconsistent parameter naming across services, which is easy to
get wrong: the catalogue search wants **`merchant`** (`merchantCode`
returns 422 there), while the review endpoint wants **`merchantCode`**.

The profile payload carries everything the actor advertises in one call:
`name`, `level`, `official`, `activationDate`, `province`,
`respondTimeRating`, `productQualityRating`, `orderFullfilmentRating`, a
`badge` object (tier plus `fastCustomerResponseRating`,
`orderCompletedRating`, `deliveryRating`, `positiveFeedbackRating`,
`perfectTransactionRating`, `calculationDays`), and a `pickupPoint` object
with full address, city, lat/long, FBB flag and per-day business hours.

### Endpoints that looked useful and were not

- `/backend/customer-chat/customer/chat/get-merchant/{code}` returns only
  `{"sellerMpp": false}` — not a response-speed metric. Response speed is
  `respondTimeRating` on the profile instead.
- `/backend/product-pickup-point/merchants/{code}/pickup-points` requires a
  `selectedPickupPoint` query parameter, and having supplied one it just
  echoes that pickup point back with `totalPickupPointsCount: 0`. The
  profile's own `pickupPoint` object is richer.
- `/backend/common/content/merchant-rating-info-{code}` returns
  `418 I_AM_A_TEAPOT`.

## A nonexistent store returns 200, not 404

Querying a made-up code (`ZZZ-99999`, `COP-99999`, `NOPE-1`) returns **200
with a fully-shaped but hollow profile**: every rating `0.0`,
`official: false`, an empty `url`, and **no `name`**. Emitted unchecked,
that is a perfectly valid-looking `MERCHANT_PROFILE` row full of zeros —
which would quietly corrupt a competitor benchmark. The presence of `name`
is the discriminator, and its absence raises `STORE_NOT_FOUND`.

## The catalogue caps at 800 products per query

`/backend/search/products` serves at most 20 pages regardless of page size,
so one query slice tops out at 800 products. Most stores fit inside that
comfortably (measured: 154 and 187 products); large ones do not — adidas
Sports Flagship Store reports **3,112**.

Extra query slices each open their own 800-product window. Measured on the
3,112-product store:

| Slice | Unique | New |
| --- | --- | --- |
| unfiltered | 800 | 800 |
| `sort=3` (cheapest) | 800 | +489 |
| `sort=4` (most expensive) | 800 | +437 |
| `sort=16` (best selling) | 800 | +43 |
| price bands (5) | — | +502 |
| **combined** | **2,271** | of 3,112 (73%) |

`sort=5` and `sort=6` added nothing (they duplicate other orderings), so
they are not in the plan. Seller-catalogue (`sc`) slices also work but are
small — 3 to 69 products each — so they are not worth the request budget
against the price/sort slices.

`deep` coverage runs the sort and price-band slices; `standard` runs one
sweep, which is the complete catalogue for the majority of stores. The
profile's `productCount` always reports the true catalogue size, so a
consumer can always see how much of it a run actually retrieved.

## Known limits

- **A very large catalogue cannot be fully enumerated** — roughly 73% at
  best on a 3,000-product store. `productCount` states the true total.
- No absolute stock levels; `soldCount` is the demand proxy Blibli exposes.
- The profile is a point-in-time snapshot; badge scores are calculated over
  a rolling window Blibli reports as `calculationDays` (180 in samples).
