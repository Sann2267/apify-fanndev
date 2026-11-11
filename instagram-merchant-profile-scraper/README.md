# Instagram Merchant Profile & Bio-Link Extractor

Extract public Instagram business profiles — followers, engagement, business
contact details, and the **bio links that are a merchant's actual
storefront** (Shopee, Tokopedia, WhatsApp, Linktree, own webstore).

For competitor mapping, seller research and lead generation.

No login, no API key. HTTP-only — no browser.

## ⚠️ This does not scrape an Instagram Shop

If you came here for Instagram Shop products or a product catalog: **that
data is no longer public.** Verified anonymously on 2026-09-01 —
`/<user>/shop/` and `/explore/shop/` redirect to the login page, five major
retail accounts carry zero shopping/catalog fields, and there is no product
tagging on posts (`product_type` is only ever `clips`/`igtv`, which is the
*media* type). Meta wound Instagram Shopping down.

No amount of scraping technique recovers data a platform stopped publishing,
so this actor extracts what genuinely is public — and for a merchant, the
bio link **is** the shop.

## Output

```json
{
  "username": "cottonink",
  "fullName": "COTTONINK | Jakarta",
  "biography": "Now Available:\nFall Collection 2026🍂 ...",
  "isVerified": true,
  "followers": 680168,
  "following": 150,
  "postCount": 7483,

  "bioLinks": [
    { "url": "http://linktr.ee/COTTONINK", "title": "Shop Now!",
      "linkType": "external", "platform": "LINK_AGGREGATOR" }
  ],
  "primaryShopLink": "http://linktr.ee/COTTONINK",
  "linkPlatforms": ["LINK_AGGREGATOR"],
  "marketplaces": [],
  "sellsOnMarketplace": false,
  "hasWhatsApp": false,

  "_source": "S2-profile-html"
}
```

With the API strategy you additionally get business contact and posts:

```json
{
  "isBusinessAccount": true,
  "businessContactMethod": "CALL",
  "businessCity": "Beaverton, Oregon",
  "businessLatitude": 45.5076448,
  "avgEngagementPerPost": 187959.7,
  "engagementRatePercent": 0.0645,
  "recentPosts": [
    { "shortcode": "DctPchKOVcw", "likes": 277530, "comments": 1935,
      "mediaType": "clips", "takenAt": "2026-08-31T13:56:44Z" }
  ]
}
```

Instagram's `l.instagram.com` redirect wrapper is unwrapped, so `bioLinks`
carry the real destination, deduplicated, each labelled with the platform a
merchant is actually selling on.

## Input

```json
{
  "usernames": ["cottonink", "@nike", "https://www.instagram.com/hijup/"],
  "includeRecentPosts": true,
  "delaySeconds": 2
}
```

| Field | Description |
| --- | --- |
| `usernames` | Handles or profile URLs; `@` and query strings are handled |
| `includeRecentPosts` | Attach recent posts and compute engagement rate |
| `maxPostsPerProfile` | Cap attached posts (Instagram returns ~12 anonymously) |
| `delaySeconds` | Pause between accounts — pacing keeps a run alive |
| `proxyConfiguration` | Residential **strongly recommended** |

## Read this before relying on the output

**Three strategies, and the richest one is the minority path.** The actor
tries the JSON API (S1), then the page's embedded JSON (S2), then `og` meta
tags (S3), and records which one produced each row in `_source`.

In a 3-account test run, **2 of 3 accounts fell through to S2**. That matters
because:

- `businessEmail`, `businessPhone`, `businessContactMethod`, the business
  address fields and `recentPosts` come from **S1 only**. On S2 rows they are
  empty — not because the merchant has none, but because that source doesn't
  carry them.
- S3 rows have **rounded** counts (`680000` rather than `680168`) and are
  tagged `_warning: counts_are_rounded_og_values`.

Filter on `_source` if you need guaranteed business contact data.

**Instagram throttles anonymous traffic hard**, and signals it with a 200
that redirects to a login wall rather than a clean 429. Profiles are
therefore fetched sequentially with a delay, and a block rotates both the TLS
fingerprint and the proxy session. Without a residential proxy expect login
walls after a handful of accounts.

## Known limits

- **No shop/product/catalog data** — see above.
- Business contact and posts only on S1 rows.
- `og` counts are rounded, and flagged when used.
- `engagementRatePercent` is computed over the ~12 fetched posts — a recent
  sample, not a lifetime average.
- Private accounts expose no posts; Instagram CDN media URLs are signed and
  expire, so download promptly if you need the images.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the full evidence on the
missing shop surface, the strategy comparison, and the rate-limit behaviour.
