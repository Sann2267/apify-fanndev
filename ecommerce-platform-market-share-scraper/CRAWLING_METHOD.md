# Crawling method - storeleads.app public reports

Recon date: **2026-09-18**, plain HTTP, no proxy, no cookie, no account.

## Why this target and not the store database

The research note that led here pointed at the per-store database (the product
`saswave/storeleads-scraper` sells, with a 76% failure rate). Recon killed that
idea and found a better one:

| Path | Anonymous result |
|---|---|
| `/domain/gymshark.com` | **404** |
| `/apps/klaviyo` | **404** |
| `/reports` | **200**, index of **110** platform reports |
| `/reports/shopify` | **200**, 102 KB, fully server-rendered |
| `/reports/bigcommerce` | **200**, 91 KB |

Per-store data is behind a paid account, so it is out of scope on purpose. The
**reports** are public, rich, and nobody in the vein sells them as structured
rows.

## What one report contains

16 sections, each with an `id` anchor, verified on `/reports/shopify`:

`growth` (31 quarters, 2019 Q1 -> today) · `socialmedia` · `contactinfo` ·
`topcategories` · `topcountries` · `topapps` · `employees` · `products` ·
`toptechnologies` · `shipping` · `themes` · `tlds` · `topstores` ·
`newstores` · `windomains` (switched in) · `lossdomains` (switched out).

Headline numbers live in prose, not in a table: "there are 3,077,514 live
stores", "increased 7.3% quarter-over-quarter in 2026 Q2", "Updated Sep 11
2026". They are read with narrow regexes over the page text.

## Gotchas found (and handled in code)

1. **There are no `<table>` elements.** The layout is `div.table > div.row >
   div.cell[data-title]`. A table parser returns zero rows. Parsing keys off
   `data-title`, the attribute the site itself uses for mobile labels, so the
   column meaning survives a layout change that would break positional parsing.
2. **Section slices must be bounded.** Anchors and tables are siblings in one
   long document; parsing from an anchor to the end of the page makes one
   section swallow the next section's rows. The parser cuts at the next `id="`.
3. **The newest quarter appears twice** - once in a callout above the table and
   once as the table's last row - and the callout copy sorts first, which would
   put a partial quarter at the head of a time series. Rows are de-duplicated on
   quarter keeping the *last* occurrence.
4. **Cell text is pretty-printed across lines**: `"2026 Q3\n\n  (to date)"`.
   Whitespace is collapsed at parse time so the dataset never carries layout.
5. **`(to date)` marks an in-progress quarter.** Kept as a boolean flag rather
   than silently dropped, because a consumer charting it as complete would read
   a partial quarter as a decline.
6. **Every dimension exists twice**: as the visible table and as a JS array
   (`countryData`, `themeData`, `attritionData`, ...). The table is primary
   because it is what the publisher displays; the JS array is used only to
   attach machine codes the table drops (`US`, `com`). Where they disagree, the
   table wins.
7. **One request hung past 30 s** while its siblings answered in under a
   second. Timeout is 60 s and a timeout is treated as transient, not as a block.
8. **404 is definitive** - the site serves a 20 KB "Not Found" page for unknown
   slugs, and retrying it is pure waste.

## Verified numbers (2026-09-18)

| Platform | Live stores | Quarters of history | QoQ | YoY |
|---|---:|---:|---:|---:|
| Shopify | 3,077,514 | 31 | 7.3% | 11% |
| WooCommerce | 4,056,316 | 27 | - | - |
| BigCommerce | 36,646 | 31 | - | - |

Shopify migration sample: 8,728 stores switched in from WooCommerce, 6,006
switched out to it - both directions published, so net flow is computable.

## Not implemented (deliberately)

- **The paid store database** (`/domain/...`, exports, the API) - behind an
  account, therefore out of scope.
- **Blog posts** at `/blog` - prose, not data.
