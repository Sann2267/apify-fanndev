# Crawling method: Steam Community Market (recon 2026-10-11)

## Surface

`steamcommunity.com` is plain nginx with **no WAF**. Every curl_cffi profile tested
(chrome124, safari17_0, chrome99_android, edge101, chrome131) gets 200. robots.txt only
disallows `/actions/ /linkfilter/ /tradeoffer/ /trade/ /email/`. `/market/` is allowed
(note: `/market/actions` is not under `/actions/`).

In 2026 the market became a React SSR app. Listing pages embed `<script id="valve-ssr-data">`
(about 4 MB) holding a dehydrated React Query cache: price history for **every variant** of
the skin, descriptions, one order book, the first listings page and the app facets. Do not
scrape that page. The bundle's RPC layer serves the same data in small pieces.

## RPC transport (from bundle module `CX9_2ETe.js`)

```
query:     GET  <route>?q=<Method>&qp=<JSON array of args>   header x-valve-request-type: queryAction
mutation:  POST <route> body {"m": <Method>, "mp": [args]}   header x-valve-request-type: mutationAction
response:  {"data": ..., "metrics": ...}
```

The header is not enforced today, but we send it anyway.

| Route / method | Args | Anonymous? | Notes |
| --- | --- | --- | --- |
| `/market/actions` `Search` | `{appid, strQuery, filters:{cat:[tags]}, price:{unMin,unMax,eCurrency}, sort, direction, start, count}` | yes | count=100 honoured; **always USD**; grouped by bucket (`grouping:1`), `disableGrouping` ignored; deep paging to the end (13,344 for CS2); appid required (`data:null` without it) |
| `/market/actions` `QueryPriceHistory` | `appid, hash_name` | **yes** | legacy `/market/pricehistory/` = 400 without login. Daily since first sale, hourly for the last ~month. `price_median` in major units |
| `/market/orderbook` `Load` | `appid, hash_name` | yes | full depth: `rgCompact{Buy,Sell}Orders = [price, qty, ...]` in hundredths. Unknown item → `{success:false}` |
| `/market/actions` `QueryListingsForItem` | `{appid, strItemName, filters, accessoryFilters, propertyFilters, start, sort, disableGrouping}` | yes | **20/page fixed**. Hash name needs `disableGrouping:true` (otherwise total 0). Bucket id `G...` works without it. Pages to the very end |
| `/market/actions` `QueryDescription` | `appid, hash_name` | yes | unknown → `data:null`; carries `market_bucket_group_id` |
| `/market/actions` `QueryRecentSales` | none | yes | 50 global sales, cache refreshes about every 30 s. Sold listing `unPrice` is always 0; the real price is `strSoldPrice` (viewer currency) |
| `/market/listings/<app>/<name>` + headers `x-valve-request-type: routeData`, `x-valve-loader-index: 3` | none | yes | 3 KB JSON with `buckets[]`, the variant list of a group. Follows the hash→`G…` redirect |

Search sort (mapped empirically): 0 popular, 1 name (dir 1 = A-Z), 2 quantity (dir 0 = most),
3 price (dir 1 = ascending).

Listing sort: `{field:0 price | 1 asset property, direction:0 asc, assetpropertyid:2 float | 1 seed}`.

## Gates and limits

- **Currency = exit-IP country.** Cookies (`steamCountry`, `steamCurrencyId`), `?cc=`,
  `?country=`, `?currency=` are all ignored, and a 3rd RPC arg returns 400. Only the proxy country
  changes it. Search is the exception (always USD).
- **Rate limit:** 80 back-to-back RPC calls from one residential IP drew 0 × 429. Legacy
  `priceoverview` returned 429 from call 21. Hence RPC-only.
- Amounts: integers in hundredths (IDR included). `unPrice + unFee` = buyer price.
- Thin hourly history points (1 sale) make raw max/min meaningless. ATH/ATL are computed on daily VWAP.

## Dead / changed legacy surfaces

- `/market/search/render/?norender=1`: still 200, but pagesize capped at 10.
- `/market/popular`: `{"success":false,"stop":true}`.
- `/market/listings/.../render/`: now returns the SSR HTML page, not JSON.
- `Market_LoadOrderSpread(item_nameid)` / `var line1=`: gone from the page. `itemordershistogram`
  still works with an old item_nameid, but there is no anonymous way to discover new ids.
