# Crawling method — Amazon Best Sellers

Recon date: **2026-09-01**. Every figure below was measured live.

## Access: no browser needed

The mandatory profile ladder was run before assuming anything about Amazon's
defences. **Every profile returned 200 with the bestseller grid** — no
CAPTCHA, no bot wall, no interstitial:

| Profile | Result |
| --- | --- |
| chrome124 / chrome131 / chrome116 | 200, grid present |
| chrome99_android | 200, grid present |
| safari17_0 / safari18_0 | 200, grid present |
| firefox133 / edge101 | 200, grid present |

Amazon does serve CAPTCHAs to traffic it dislikes, so the client detects them
by **body marker** (`Robot Check`, `Enter the characters you see below`,
`/errors/validateCaptcha`) — they arrive with HTTP 200, so status alone is
useless. Per this project's no-captcha-solver policy a CAPTCHA is retried
with a rotated fingerprint and IP, then reported as `CAPTCHA_ESCALATION`
rather than solved.

## The extraction spine

Each list page carries a `data-client-recs-list` attribute holding a JSON
array of **all 50** entries on that page:

```json
{"id": "B08JHCVHTY",
 "metadataMap": {"render.zg.rank": "1",
                 "render.zg.bsms.currentSalesRank": "",
                 "render.zg.bsms.percentageChange": "",
                 "render.zg.bsms.twentyFourHourOldSalesRank": ""}}
```

This is preferred over CSS selectors: Amazon's class names are hashed and
churn, while this attribute is stable and complete. Two pages (`?pg=2`) give
a clean **100 unique ASINs, ranks 1–100** — verified.

## Only 30 of 50 tiles render, and the crawler view is a trap

The product tiles carrying title/price/rating/reviews are server-rendered
for only ~30 of the 50 entries; the rest lazy-load. So a 100-rank run yields
100 ranked ASINs and about 60 with full details. `hasDetails` marks each row.

A crawler User-Agent renders all 50 tiles — which looks like a strict
improvement and is not. Measured field coverage:

| View | Tiles | title | price | rating | reviews |
| --- | --- | --- | --- | --- | --- |
| Normal browser | 30 | 30/30 | **29/30** | **30/30** | **30/30** |
| Crawler UA | 50 | 50/50 | **0/50** | **0/50** | **0/50** |

The crawler view is a stripped SEO page: more rows, none of the fields that
matter for product research. The normal browser identity is therefore used
deliberately. Worth knowing before anyone "optimises" this by switching UA.

## Amazon's own Movers & Shakers is empty

`/gp/movers-and-shakers/<category>` returned **no products in every category
tested** — electronics, books, toys-and-games, home-garden, beauty — each
serving the literal message *"Sorry, there are no movers and shakers
available in this category. Please check back later."* with
`data-client-recs-list="[]"`. The root pages (US, UK, DE) carry no
recs-list at all. The `render.zg.bsms.*` metadata fields exist in the schema
but were empty on every page seen.

The actor still reads those fields when present, and still lets you request
that list type — but it computes movement itself from rank snapshots
between runs. That is more dependable than a page Amazon is not populating,
and it is what makes this a *tracker*.

Requesting `listType: movers-and-shakers` therefore fails with a
`NOT_FOUND` row that names the working alternative rather than returning an
empty dataset.

## Movement detection

The previous run's ranks live in a **named** key-value store (default
`amazon-rank-state`), keyed `marketplace|listType|category`, so several
watchlists stay independent and the state survives scheduled runs.

`rankChange` is `previousRank - rank`, so a **positive number means the
product climbed** (a lower rank is better). Products are classified
`NEW_ENTRY`, `RISING`, `FALLING`, `UNCHANGED` or `DROPPED_OUT`, and moves
under 5 ranks are marked insignificant — a top-100 list reshuffles
constantly and single-rank wobble is noise.

`DROPPED_OUT` rows come from diffing the snapshot against the current list,
so products that fell out of the top 100 are visible at all — they appear
nowhere on the page by definition. Lists absent from a given run keep their
previous history rather than being erased.

## Sibling lists

`/gp/new-releases/<category>` and `/gp/most-wished-for/<category>` use the
identical structure (50 recs entries, 30 rendered tiles) and are exposed as
list types. Sub-categories work via node paths, e.g.
`electronics/172541` → `/Best-Sellers/zgbs/electronics/172541`.

## Known limits

- **Rank 100 is the ceiling.** Amazon serves 50 per page and stops at two
  pages.
- **~40% of rows carry rank + ASIN only** — see the tile-rendering split
  above. `hasDetails` says which.
- Amazon's own Movers & Shakers metrics are empty in practice.
- A run is a point-in-time snapshot; movement quality depends entirely on
  run cadence, so schedule it consistently (for example daily at the same
  hour).
