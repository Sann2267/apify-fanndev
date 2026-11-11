# Crawling method — Blibli affiliate content

Recon date: **2026-09-01**. Every claim below was measured live.

## What "affiliate link" actually means here

This is the honest core of the actor, so it is stated first.

| Endpoint | Result |
| --- | --- |
| `POST /backend/affiliate/share-link` | **200, public** — no cookie, no login |
| `POST /backend/affiliate/session` | 200 (returns `{"code":200,"status":"OK"}`, no payload) |
| `POST /backend/affiliate/commission` | **401 UNAUTHORIZED** |
| `/member/p/affiliate` | member-only route |

So Blibli's **commission attribution requires an authenticated affiliate
account**, which is out of scope under this project's no-login constraint.
What *is* public is the share-link minter — the site's own config names it
`appFlyersOneLink`, i.e. AppsFlyer OneLink.

Given `{"url", "pageType", "campaign", "source", "medium", "platform"}` it
returns e.g. `https://blibli.onelink.me/GNtk/gryz5myg`, which resolves to:

```
https://www.blibli.com/p/<slug>/is--<SKU>?utm_campaign=…&utm_medium=…&utm_source=…
```

— the supplied values, carried through verbatim. Therefore the actor
produces **tracking links, not commission links**, and says so in the
README and the output schema rather than implying otherwise. A marketer
with a Blibli affiliate/creator ID puts it in the UTM values.

Details found by probing:

- `pageType` accepts **only `PRODUCT_DETAIL`**. `SEARCH`, `MERCHANT`,
  `HOMEPAGE`, `CATEGORY`, `PROMO` and `BRAND` all return `400 InvalidFormat`.
- All six fields are mandatory — omitting any yields
  `400 {"errors":{"campaign":["NotBlank"], …}}`.
- **Minting is deterministic**: an identical payload returns an identical
  short link, so re-running an unchanged job does not create link sprawl.
  Changing any one of campaign/source/medium yields a different link.
- Throughput measured at ~0.65 s per link, 12/12 successful.

## WAF profile

Cloudflare, with a mandatory `Referer` header, as on every Blibli surface.
The TLS ladder leads with `safari17_0`: a sibling actor established that
Chrome fingerprints are specifically blocked on some `/backend/search/*`
paths, and `safari17_0` is verified against everything used here.

Worth recording: **sustained recon from a single IP drew intermittent 403s**
that cleared on retry with a rotated fingerprint. That is why the client's
backoff and profile rotation matter here, and why residential proxy is
recommended rather than merely offered — this actor makes up to three
requests per product (search page, link mint, optional page enrichment).

## Sourcing high-quality products

All filters are Blibli's own facets, pushed server-side so pagination is
spent only on products that already qualify:

| Goal | Parameter | Note |
| --- | --- | --- |
| Best sellers | `sort=16` | "Terlaris" |
| High rating | `rating=4` or `3` | The facet advertises only 3 and 4, so a stricter threshold is enforced client-side against each product's real rating |
| Original, officially warranted | `warrantyType=Garansi Resmi` | 509 laptops matched at the time of recon |
| Top sellers | `seller=Top rated seller` | |
| Discounted | `discount=10\|25\|50\|75` | Buckets meaning "at least"; the exact figure is enforced client-side |

Measured funnel for `laptop gaming` sorted by best selling: 1,485 products
→ 123 at 4★ → 66 with an official warranty. Those 66 mostly carry only
1–7 reviews, so a `minReviewCount` of 10 legitimately empties the result —
the actor emits an `EMPTY_RESULT` diagnostic naming which filter to loosen
rather than a silent empty dataset.

The search backend caps at 20 pages regardless of page size, so one query
yields at most 800 products.

## Content extraction

- **`uniqueSellingPoint`** is a single string with literal `\n<br>`
  separators and `•` glyphs, e.g.
  `"• Processor : Intel Core i3-1315U \n<br>• Memory : 8GB"`. It is parsed
  into clean bullet strings and then assembled into a length-bounded
  `shortDescription`.
- **Images** carry their size inside the path
  (`/catalog/medium/catalog-image/…`). Swapping the segment works for
  `medium`, `full` and `thumbnail`; `large` and `small` both 404. `full` is
  the default here since posts want the large asset.
- **Product URLs from search results carry session junk** —
  `?ds=…&source=SEARCH&sid=…&metaData=…`. That is stripped before any link
  is built, so a shared link never leaks another session's tracking.
- **Warranty text is not in search results** (`warranty: null` there). It
  exists only on the product page, inside
  `window.__PRODUCT_DETAIL_INITIAL_STATE__` at
  `productDetail.product/summary.warranty`, as
  `{"type": "RESMI", "text": "Garansi resmi 2 tahun", "duration": "2 tahun"}`.
  Extracting it needs a balanced-brace walk over the inlined object, since
  further statements follow it in the same `<script>` block. That page also
  yields Blibli's own `seo.metaDescription`, a usable marketing blurb. Both
  are behind the optional `enrichFromProductPage` flag because they cost one
  request per product.

## Known limits

- **No commission attribution** — see the top of this document.
- 800 products per query; widen with more search terms or categories.
- `shortDescription` is derived from seller-supplied spec bullets, so its
  quality varies by listing; `seoDescription` (enrichment) is often the
  better prose.
- Product data is Indonesian-language.
