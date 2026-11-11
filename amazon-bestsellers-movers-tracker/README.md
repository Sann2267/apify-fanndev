# Amazon Best Sellers & Movers Tracker

Track the **top 100 Best Sellers** in any Amazon category or sub-category —
and see exactly **what moved since your last run**: climbers, new entries and
products that dropped out.

Built for FBA sellers and affiliates doing winning-product research, where
the interesting signal is not "what is #1 today" but "what is climbing fast".

No login, no API key. HTTP-only — no browser.

## What a run gives you

```json
{
  "rank": 41,
  "asin": "B088Z22VYF",
  "title": "Fire TV Stick 4K streaming device",
  "price": 24.99,
  "rating": 4.6,
  "reviewCount": 412903,
  "productUrl": "https://www.amazon.com/dp/B088Z22VYF",

  "previousRank": 71,
  "rankChange": 30,
  "movementType": "RISING",
  "isNewEntry": false,
  "isSignificantMove": true,

  "category": "electronics",
  "listType": "bestsellers",
  "marketplace": "com",
  "hasDetails": true
}
```

`rankChange` is **positive when a product climbs** (a lower rank number is
better). Set `onlyMovers: true` and the dataset contains just the shortlist:

```
RISING       rank=41  prev=71  change=+30   Fire TV Stick 4K
FALLING      rank=6   prev=1   change=-5    Fire TV Stick 4K Plus
NEW_ENTRY    rank=81  prev=—   change=—     (new to the top 100)
DROPPED_OUT  rank=—   prev=77  change=—     (fell out of the top 100)
```

`DROPPED_OUT` products appear nowhere on Amazon's page by definition — they
are only visible by diffing against the previous run.

## ⚠️ About "Movers & Shakers"

Amazon's own Movers & Shakers pages returned **no data in any category
tested** (electronics, books, toys, home, beauty), each showing *"Sorry,
there are no movers and shakers available in this category."*

So this actor **computes the movers itself** from rank snapshots between
runs, which is more dependable than a page Amazon isn't populating — and
gives you drop-outs too, which Amazon's page never showed. Amazon's own
`percentageChange` fields are still read and passed through when present;
they were empty throughout testing.

You can still select `listType: movers-and-shakers`; it will fail with a row
telling you to use `bestsellers` rather than returning an empty dataset.

## Input

```json
{
  "categories": ["electronics", "toys-and-games", "electronics/172541"],
  "listType": "bestsellers",
  "marketplace": "com",
  "maxRank": 100,
  "trackMovement": true,
  "onlyMovers": false
}
```

| Field | Description |
| --- | --- |
| `categories` | Slugs, sub-category node paths (`electronics/172541`), or full Amazon list URLs — a URL overrides marketplace and list type, so one run can mix marketplaces |
| `listType` | `bestsellers` (recommended), `new-releases`, `most-wished-for`, `movers-and-shakers` |
| `marketplace` | com, co.uk, de, fr, it, es, ca, com.au, co.jp, in |
| `maxRank` | Up to 100 (Amazon's ceiling). 50 costs one request, 100 costs two |
| `trackMovement` | Compare against the previous run and label every product |
| `onlyMovers` | Emit only significant moves, new entries and drop-outs |
| `includeDroppedOut` | Emit rows for products that left the list |
| `stateStoreName` | Named store for the snapshot — use different names for independent watchlists |
| `delaySeconds` | Pacing; Amazon serves CAPTCHAs to traffic it dislikes |
| `proxyConfiguration` | Residential recommended for scheduled runs |

## Read this before relying on the output

**About 40% of rows carry rank + ASIN only.** Amazon server-renders just 30
of the 50 product tiles per page; the rest lazy-load. Every product in the
top 100 gets `rank`, `asin` and `productUrl` — but `title`, `price`,
`rating` and `reviewCount` cover roughly 60 of 100. **`hasDetails` marks
which rows are complete**, so filter on it if your pipeline needs price.

(A crawler User-Agent renders all 50 tiles, but that view drops price,
rating and reviews entirely — measured 0/50 on each. More rows, less data,
so it isn't used.)

**Movement quality depends on run cadence.** On the first run everything is
`NEW_ENTRY` because there's nothing to compare against. Schedule it
consistently — daily at the same hour works well — and the deltas become
meaningful.

**CAPTCHAs are reported, never solved.** If Amazon challenges a request the
actor retries with a rotated fingerprint and IP, then emits
`CAPTCHA_ESCALATION` for that list and carries on with the others.

## Known limits

- **Rank 100 is Amazon's ceiling** — no deeper list is served.
- Detail coverage ~60% per the tile split above.
- Amazon's own Movers & Shakers metrics are empty in practice.
- One snapshot per list per run; sub-hourly cadence will mostly capture noise
  rather than signal.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the profile ladder results,
the crawler-UA trade-off measurements, and the Movers & Shakers evidence.
