# Crawling method — Blibli product sync

Recon date: **2026-09-01**. Every claim below was measured live.

## The finding that shapes this actor

`/backend/product/products/_basic` is a genuine **bulk** endpoint — `sku=`
takes a comma-separated list (or repeated params) and 100 distinct SKUs
resolved in a single call. That is what makes syncing a large reseller
catalogue cheap: one request per 50 SKUs instead of one per product.

**But it silently omits some products that are perfectly alive.**

`VAM-43292-00654` returns `{"data": []}` from `_basic` — alone or in a
batch — while at the same moment:

- search lists it as `status: AVAILABLE, buyable: true`, and
- its product page shows a real listing, **stock 6**, price Rp891,000.

A missing SKU is therefore **not** evidence that a listing was removed. An
actor that assumed otherwise would tell a dropshipper to unpublish products
that are still on sale — a false signal that costs real revenue. So every
SKU absent from the bulk response is re-checked against its product page
before this actor will report `NOT_FOUND`, and `verifyMissing` defaults to
on. With verification explicitly disabled, the row still says in
`_errorDetail` that the absence was **not** confirmed.

Genuinely absent SKUs are distinguishable: a bogus SKU's page returns ~21 KB
with **no** `__PRODUCT_DETAIL_INITIAL_STATE__`, versus ~240 KB with full
product state for a real one.

## Reaching a product from its SKU alone

The slug segment of a product URL is ignored — `/p/x/ps--<SKU>` resolves any
product, returning the same page as the canonical URL. Verified against
three different SKUs. That means a reseller only has to store SKUs; the
actor never needs to know or persist product URLs.

## What each source gives you

| Field | Bulk (`_basic`) | Product page |
| --- | --- | --- |
| name, brand, merchant | yes | yes |
| price / list price / discount | yes | yes |
| availability | **boolean only** (`stock: true`) | — |
| **stock quantity** | no | **yes** (e.g. `96`) |
| low-stock threshold | no | yes |
| description (`uniqueSellingPoint`) | no | yes |
| warranty text | no | yes |
| categories, all images | no | yes |
| pre-order flag | no | yes |
| cost | 1 request per 50 SKUs | 1 request per SKU |

Hence the two modes: fast mode for frequent price/availability syncs,
detailed mode when copy and exact stock levels are also needed.

Field-name note: the bulk endpoint returns `price.offered` / `price.listed`
/ `price.salePrice` / `price.discount`, while the product page uses
`price.offered` / `price.listed` / `price.totalDiscount`. Both are mapped
onto one output shape so a consumer never has to branch on the source.

The description arrives as a single string with literal `\n<br>` separators
and `•` glyphs; it is cleaned into plain lines before output.

## Change detection

The previous run's snapshot is kept in a **named** key-value store (default
`blibli-sync-state`, key `SNAPSHOT`) rather than the default store, so it
survives between scheduled runs. Only five fields per SKU are retained —
price, inStock, stockQuantity, name, syncStatus — which keeps the snapshot
small for a large catalogue.

Each run classifies every SKU as `NEW`, `UNCHANGED`, `PRICE_INCREASED`,
`PRICE_DECREASED`, `OUT_OF_STOCK`, `BACK_IN_STOCK`, `NAME_CHANGED`,
`BECAME_UNAVAILABLE` or `BECAME_AVAILABLE` — several can apply at once —
and emits per-field before/after values with a percentage delta on price.

SKUs not included in a given run are **carried forward** rather than dropped
from the snapshot, so syncing a subset of the catalogue does not erase the
rest of its history.

## WAF profile

Cloudflare, `Referer` mandatory, ladder leading with `safari17_0` (a sibling
actor established Chrome fingerprints are blocked on some `/backend/search/*`
paths, and the bulk endpoint returned intermittent 403s on Chrome during
recon too). Sustained recon from one IP drew repeated transient 403s that
cleared on retry with a rotated fingerprint — for a scheduled sync over a
large catalogue, residential proxy is the difference between a clean run and
a half-failed one.

## Known limits

- **Availability is a boolean in fast mode.** Exact stock needs detailed
  mode, which costs one request per SKU.
- **Variants**: `hasVariants` is reported, but per-variant price and stock
  are not enumerated — the figures describe the default variant.
- A run reflects a single point in time; prices and stock on a marketplace
  move continuously, so schedule frequency determines freshness.
