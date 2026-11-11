# Blibli Affiliate Link Generator & Content Parser

Source best-selling, well-rated [Blibli](https://www.blibli.com) products —
optionally only ones with an **official warranty** — and get back everything
a post needs: full-size images, a clean short description, a tracking link,
and a ready-to-paste caption.

Built for affiliate and content marketers who would otherwise copy this out
of the browser one product at a time.

No login, no API key. HTTP-only — no browser.

## ⚠️ Read this first: what "affiliate link" means here

This actor produces **tracking links, not commission links.**

Blibli's commission API (`/backend/affiliate/commission`) returns **401
without an authenticated affiliate account**, so commission attribution
cannot be done without a login and is out of scope for this actor.

What it *does* do, using Blibli's own **public** endpoint:

- mints Blibli's official **OneLink** short link
  (`https://blibli.onelink.me/GNtk/…`) for each product, which opens the
  Blibli app or product page; and
- stamps **your** `utm_campaign` / `utm_source` / `utm_medium` onto every
  link — which is where your affiliate or creator ID goes.

If your affiliate programme attributes on UTM values or on a link you
register yourself, this gives you exactly what you need at scale. If it
requires Blibli-issued per-marketer links, generate those in your affiliate
dashboard and use this actor for the product sourcing and content instead.

## What you get per product

```json
{
  "sku": "BLG-60035-03503",
  "name": "HP 14-ep0260TU Laptop - Gold [i3-1315U/8GB/512GB/Win11...]",
  "brand": "HP",
  "salePrice": 8999000,
  "listPrice": 9499000,
  "discountPercent": 5,
  "rating": 4.7,
  "reviewCount": 12,
  "soldCount": 335,

  "warrantyText": "Garansi resmi 2 tahun",
  "hasOfficialWarranty": true,
  "isOfficialStore": true,
  "merchantBadge": "Diamond",

  "sellingPoints": ["Processor : Intel Core i3-1315U", "Memory : 8GB DDR4-3200"],
  "shortDescription": "Processor : Intel Core i3-1315U · Memory : 8GB DDR4-3200 · ...",
  "primaryImage": "https://www.static-src.com/.../catalog/full/.../hp_..._full01.webp",

  "productUrl":  "https://www.blibli.com/p/hp-14-ep0260tu.../ps--BLG-60035-03503",
  "trackedUrl":  "https://www.blibli.com/p/...?utm_campaign=aff-budi&utm_source=instagram&utm_medium=social",
  "shareLink":   "https://blibli.onelink.me/GNtk/0jt5f7nm",

  "caption": "HP 14-ep0260TU Laptop - Gold ...\nRp8.999.000 (diskon 5%, dari Rp9.499.000)\n4.7 bintang - 335 terjual\nProcessor : Intel Core i3-1315U · ...\nhttps://blibli.onelink.me/GNtk/0jt5f7nm"
}
```

`caption` is rendered from your own template, so you can match your posting
style. Placeholders: `{name} {brand} {price} {listPrice} {discount} {rating}
{reviewCount} {sold} {warranty} {description} {link} {merchant}`.

## Input

```json
{
  "searchTerms": ["laptop", "headphone"],
  "sortBy": "bestSelling",
  "minRating": 4,
  "minReviewCount": 10,
  "officialWarrantyOnly": true,
  "generateShareLink": true,
  "enrichFromProductPage": true,
  "trackingCampaign": "aff-budi-sep2026",
  "trackingSource": "instagram",
  "trackingMedium": "social"
}
```

| Field | Description |
| --- | --- |
| `searchTerms` / `categories` | What to source from |
| `sortBy` | `bestSelling` (default), `relevance`, `cheapest`, `mostExpensive`, `newest` |
| `minRating` / `minReviewCount` / `minSoldCount` | Quality gates — a 5★ rating from 2 reviews is not a selling point |
| `minDiscountPercent` | Only products with a real discount |
| `officialWarrantyOnly` | **Garansi Resmi** only — original, officially warranted stock |
| `officialStoreOnly` / `topRatedSellerOnly` | Restrict to official brand stores / top-rated sellers |
| `generateShareLink` | Mint Blibli's OneLink per product (1 extra request each) |
| `trackingCampaign` / `trackingSource` / `trackingMedium` | Your UTM values, stamped on every link |
| `captionTemplate` | Your caption format; empty disables captions |
| `enrichFromProductPage` | Adds warranty wording, SEO description and stock (1 extra request each) |
| `imageSize` | `full` (default), `medium`, `thumbnail` |
| `maxItemsPerQuery`, `maxConcurrency` | Volume and politeness |
| `proxyConfiguration` | Residential + country `ID` **strongly recommended** |

## Notes that will save you time

- **`warrantyText` needs `enrichFromProductPage`.** Blibli's search results
  return `warranty: null`; the wording exists only on the product page. The
  `officialWarrantyOnly` *filter* works either way — it is applied by Blibli
  server-side — but quoting "Garansi resmi 2 tahun" in a caption needs the
  enrichment pass.
- **Tight filters can legitimately return nothing.** `laptop gaming` at 4★
  with an official warranty yields 66 products, but most have under 10
  reviews — so `minReviewCount: 10` empties it. The run then emits an
  `EMPTY_RESULT` row naming which filter to loosen, rather than a silently
  empty dataset.
- **Links are deterministic.** The same product with the same tracking
  values always mints the same OneLink, so re-running a job does not
  produce a pile of duplicate links.
- **Use a residential proxy for real runs.** This actor makes up to three
  requests per product, and Blibli throttles sustained traffic from one IP.

## Known limits

- **No commission attribution** — see the warning above.
- Blibli serves at most **800 products per query**; widen with more search
  terms or categories rather than a bigger `maxItemsPerQuery`.
- `shortDescription` is built from seller-written spec bullets, so quality
  varies by listing. With enrichment on, `seoDescription` is often better
  prose.
- Everything is in Indonesian.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the endpoint evidence
behind the affiliate-link statement, the measured filter funnel, and the
content-parsing details.
