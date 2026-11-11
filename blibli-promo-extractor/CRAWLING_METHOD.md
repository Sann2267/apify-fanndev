# Crawling method — Blibli promo surfaces

Recon date: **2026-09-01**. Everything below was confirmed live against
`www.blibli.com`, not inferred.

## WAF profile

`www.blibli.com` sits behind **Cloudflare** — `server: cloudflare`, a
`cf-ray` header, and a `__cf_bm` cookie on the deny response. Two
independent gates were isolated by ablation:

| Gate | Evidence |
| --- | --- |
| **TLS / JA3** | Plain `httpx` → `403` (248 KB HTML shell). `curl_cffi` with **no** `impersonate` → `403`. *Every* impersonation profile tried (`chrome124`, `chrome131`, `safari17_0`, `firefox133`) → `200`. The gate is the fingerprint itself, not a profile allowlist. |
| **`Referer` header** | With a valid JA3 but no `Referer` → `403`. Dropping `Accept`, `Accept-Language`, or any `Sec-Fetch-*` individually → still `200`. `Accept` + `Referer` alone → `200`. |

So the bypass is: **any curl_cffi impersonation profile + a `Referer`
header.** No cookie, token, signature, or login is needed on any endpoint
this actor uses. The deny page is a full storefront-looking HTML document
rather than a small error body, so block detection matches on body markers
as well as status codes.

`chrome124` leads the rotation ladder because the whole recon ran on it.
`chrome131` is deliberately *not* first — it is widely blocklisted across
other targets in this portfolio, even though Blibli accepts it.

## How the endpoints were found

`/promo/flash-sale` and `/flash-sale` are dead ends — Blibli serves a
*200-status error page* for unknown routes, so a naive status check reads
them as valid. The real page is `/flashsale`, which is client-rendered
(`window.SSR_APPS = false`) with an essentially empty
`__CONTENT_FLASHSALE_INITIAL_STATE__`, so no data can be lifted from the
HTML.

The endpoint map came from the page's own JS bundle instead. The chunk
list is inlined in the HTML as `static/js/<name>.<hash>.js`
against `window._main_staticPublicPath()`, which resolves to
`https://www.static-src.com/frontend/`. Two bundles carry the full API
table:

- `https://www.static-src.com/frontend/static/js/config.D3atzmzY.js` — the
  site-wide map (108 `/backend/...` paths).
- `https://www.static-src.com/frontend/content-flashsale/static/1.1.0-8/desktop/index.js`
  — the flash-sale module's own map.

These paths are version-hashed and **will rotate**. They are recon
artifacts only; the actor itself never fetches them. If Blibli restructures
its API, re-derive the map by repeating the two steps above.

## Endpoints used

| Mode | Endpoint | Paging | Stop condition |
| --- | --- | --- | --- |
| `flashSale` | `GET /backend/content-api/flashsale` | — | Returns the session windows; each `id` is `<startMs>-<endMs>`. |
| `flashSale` | `GET /backend/content-api/flashsale/v2/products` | `page`, 24/page | Empty `data`, a page with no new SKU, **or HTTP 404 `FLASHSALE_PRODUCT_NOT_FOUND`** — see below. |
| `promoCampaigns` | `GET /backend/content/promotions` | `page` + `itemPerPage` (50) | `paging.total_page` (440 promos over 9 pages at time of recon). |
| `discountedProducts` | `GET /backend/search/products` | `page` + `start` + `itemPerPage` (40) | `paging.total_page`, hard-capped at 20 by the backend. |

The site selects the `v2` flash sale endpoint itself via
`window._FLASHSALE_NEW_API = 'true'`.

### End-of-list is a 404, not an empty list

Paging past the last flash sale page returns:

```
HTTP 404 {"code":404,"status":"NOT_FOUND",
          "errors":{"FLASHSALE_PRODUCT_NOT_FOUND":["PRODUCT_NOT_FOUND"]}}
```

This is an **end-of-list signal, not a schema change** — and which of the
two terminators you get depends on the sort: unsorted walks ran out with an
empty `data` list at page 33, while `sort=1` 404s at page 33. The client
normalises the 404-with-`errors` case to an empty page so the caller's stop
condition fires, and still raises loudly on any *other* missing-`data`
response. A live walk yielded **768 unique products over 32 pages**.

### Search backend caps at 20 pages

`total_page` never exceeds 20 whatever the page size, and page 21 returns
`total_item: 0`. One query therefore tops out at 800 products; go wider by
adding search terms or splitting by category.

### The `discount` facet is bucketed

`/backend/search/products?discount=` only accepts **10 / 25 / 50 / 75** and
means "at least this percent off". An arbitrary user threshold is snapped
*down* to the nearest bucket (so paging is not wasted on cheap deals) and
the exact figure is then enforced client-side.

## Field-shape trap: two different price schemas

The two backends name their price fields differently. Assuming one shape
for both silently nulls every price in `discountedProducts` mode — this was
caught by the smoke test and is now guarded by a regression check.

| | Flash sale (`v2/products`) | Search (`search/products`) |
| --- | --- | --- |
| list price | `price.listValue` | `price.listPrice` |
| sale price | `price.offerValue` | `price.salePrice` |
| discount % | `price.discount` | `price.discount` |
| campaign | `flashsale.campaignCode` | `campaignInfo.code` |

`contextualPrice.discount` appears on both and is the price after stacking
payment-method and voucher promos — typically a few points deeper than the
headline discount, and the better measure of true aggressiveness. It is
frequently absent (6 of 30 rows carried it in one sample run), so it is
exposed as a nullable field rather than being treated as required.

## Non-product tiles share the product list

The flash sale list interleaves banners and digital top-up entries with
real products. A missing `sku` is the discriminator; those entries are
filtered out before paging logic runs, so they cannot corrupt the
dedup/stop conditions.

## Known limits

- Flash sale `c1Category` filtering is server-side and exact (verified:
  100% of returned rows carry the requested category, zero overlap between
  two different category sets), but the categories available change per
  session — read them from
  `/backend/content-api/flashsale/v2/facets?schedule_id=<id>`.
- The `promo` facet's campaign values (e.g.
  `campaign_CAMP-03285_5407119_FLASHSALE`) are **query-scoped** — they are
  discovered from a `showFacet=true` search response and rotate as
  campaigns start and end. Do not hard-code them.
- No stock *quantity* is exposed on these endpoints, only
  `flashsale.quota.percentage` (share of the flash-sale allocation already
  claimed) and a coarse `availabilityStatus`.
