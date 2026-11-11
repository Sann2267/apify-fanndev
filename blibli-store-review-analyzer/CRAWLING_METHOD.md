# Crawling method — Blibli store reviews

Recon date: **2026-09-01**. Every figure below was measured live.

## WAF profile

Same Cloudflare setup as the rest of `www.blibli.com`, re-verified against
the review endpoint specifically:

| Client | Result |
| --- | --- |
| `httpx`, plain TLS | **403** (~248 KB HTML shell) |
| `curl_cffi` impersonation, **no** `Referer` | **403** |
| `curl_cffi` impersonation **+ `Referer`** | **200** |

So the bypass is TLS impersonation *plus* a `Referer` header. No cookie,
token or login. Only publicly visible reviews are returned — Blibli's own
UI says as much — and reviewer names arrive pre-masked (`M***a`); this
actor never attempts to unmask them.

## Finding the endpoint (three decoys)

The review list is **not** in the site-wide API map. Three separate traps:

1. `/backend/product-review/reviews/_summary` is the only review path in
   the site-wide `config.<hash>.js`, and it returns just `{"count": 0}`
   for a merchant.
2. **`/backend/product-review/reviews` looks right and is a dead end.** It
   returns `200` with a perfectly well-formed
   `{"data":[],"paging":{"page":1,"total_page":0,"total_item":0}}` for
   *every* parameter name tried (`productSku`, `itemSku`, `productCode`,
   `sku`, `productId`, …). It is very easy to conclude "this product has no
   reviews" — the SanDisk product used for recon reports 465 reviews on its
   own page while this endpoint reports zero.
3. The product-detail module's `index.js` contains no `/backend/` paths at
   all; it is a loader.

The real endpoint lives two lazy-import hops down:
`product-detail/static/<ver>/desktop/index.js` →
`js/ProductReviewsWrapper.<hash>.js` (a 928-byte stub) →
**`js/ProductReviews.<hash>.js`**, which holds the API map:

```
review: { publicReview: `/backend/product-review/public-reviews`, ... }
```

Those chunk paths are version-hashed and **will rotate**; they are recon
artifacts only and the actor never fetches them.

## The endpoint

`GET /backend/product-review/public-reviews`

Identified by exactly one of three keys, taken from the chunk's own
`typeCode` map rather than guessed:

| Key | Scope |
| --- | --- |
| `merchantCode` | **every review for a whole store** |
| `productSku` | one product |
| `principalBrandCode` | a brand (returned 0 for every value tried) |

That `merchantCode` works is what makes this actor viable: store-wide
reviews come from one endpoint, with no need to enumerate the catalogue.

### Parameters

| Param | Notes |
| --- | --- |
| `page`, `itemPerPage` | **30 is the maximum page size.** 32+ return an empty body with no paging envelope at all. |
| `sortBy` | `POPULAR` (server default), `LATEST`, `OLDEST`, `HIGHEST`, `LOWEST` |
| `rating` | `1`–`5`. Works. `ratings` and `star` are silently ignored. |
| `topics` | `QUALITY`, `PRICE`, `SHIPMENT`, `PACKAGING`, `SERVICE`, `ORIGINALITY`, `GENERIC`. Works. `topic`, `filterTopics`, `reviewTopics` are silently ignored. |
| `hasComment` | **Real filter**, and the one that matters — see below. `withComment`, `hasContent`, `hasText`, `commentOnly` are silently ignored. |
| `hasMedia` | Photos/videos only. |

Several ignored parameters return a *plausible* response rather than an
error, so a filter must be validated by comparing returned IDs against an
unfiltered baseline, not by checking that the request succeeded.

## The ~600-review window, and how the actor gets past it

`total_item` is always `itemPerPage x 20`, i.e. the server exposes about
**600 reviews per distinct query** no matter how many exist. Colgate
Palmolive's store has **68,842**.

Two behaviours make naive paging dangerous:

- The server advertises `total_page: 20` but will still serve page 21.
- **Past the end it repeats earlier reviews instead of returning an empty
  list.** Stopping on "empty page" therefore never fires; the walk has to
  dedupe by review ID and stop on "no new IDs", or it runs forever.

Because each *distinct query* gets its own window, slicing the same target
opens more windows. Measured on `COP-60023`:

| Sweep | Unique reviews | New |
| --- | --- | --- |
| unfiltered | 600 | 600 |
| `rating=1` | 292 | 292 (of 294 that exist) |
| `rating=2` | 203 | 203 (of 203 that exist) |
| `rating=3` | 546 | 546 (of 549 that exist) |

Every rating slice returned **100% new** reviews, and for the low-star
slices it returned essentially *all* of them. This is why `deep` coverage
captures nearly complete negative feedback from a store with 68k reviews.

### Sweep ordering matters more than it looks

These stores run ~98% positive, so an unfiltered-first plan spends a
capped budget almost entirely on praise. Measured on a 120-record run:

| Plan | Negative reviews captured |
| --- | --- |
| unfiltered first | **5** |
| rating-stratified first | **121** |

and on a 900-record deep run, 13 → 283. The union is identical when
uncapped; the ordering only changes what a *capped* run gets, and that is
the difference between a usable complaint sample and a wall of 5-star
reviews. Ratings are swept ascending for the same reason.

## About half of all reviews have no text

`summary.commentCount` vs `summary.count`: **32,843 of 68,842 (47.7%)**
Colgate reviews carry any words at all. Worse, text density depends
heavily on sort order:

| `sortBy` | Reviews with text (of 30) |
| --- | --- |
| `LATEST` | 4 |
| `HIGHEST` | 4 |
| `LOWEST` | 2 |
| `POPULAR` | 29 |
| `OLDEST` | 30 |

`hasComment=true` filters to text-bearing reviews **server-side** — with
`sortBy=LATEST` it takes density from 4/30 to 30/30 and returns a
genuinely different result set. Without it, a sentiment run would spend
its whole 600-review window on star-only rows. This is the actor's
`onlyWithText` option, on by default.

## Aggregates come free

One `itemPerPage=1` call returns a `summary` covering the store's **entire**
review base, not the sampled window: rating histogram, average, comment
count, and Blibli's own topic classification with counts —
`QUALITY 1181, PRICE 1006, SHIPMENT 935, PACKAGING 627, SERVICE 220,
ORIGINALITY 213, GENERIC 776`. That is the "what do customers keep
complaining about" signal without any AI pass, and it is the cheapest call
in the actor.

## Store metadata and catalogue

There is **no public merchant-metadata endpoint** — `/backend/merchant/…`,
`/backend/seller/…`, `/backend/merchant-api/…` all return the HTML app
shell. The store's display name is read off its catalogue instead, via
`/backend/search/products?merchant=<CODE>` (note: `merchant`, not
`merchantCode` — the latter returns 422 there, while the review endpoint
wants exactly the opposite spelling).

## Known limits

- **~600 reviews per query slice.** A store with 68k reviews cannot be
  fully extracted; `deep`/`maximum` coverage and `productBreakdown` widen
  the sample, and the summary row still describes the whole base.
- `principalBrandCode` returned 0 results for every value tried, so brand
  targets are accepted but may legitimately yield nothing.
- No reviewer identity beyond Blibli's own masked display name.
- Reviews are Indonesian-language; downstream sentiment models should be
  multilingual.
