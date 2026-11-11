# Crawling Method — Gulf News

**Last verified:** 2026-08-24

## WAF

`gulfnews.com` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on homepage, article pages, and the news sitemap -- no
challenge body, no 403.

`robots.txt` has no Claude/GPTBot/anthropic-ai disallow -- notably unlike
Khaleej Times, Haaretz, and Jerusalem Post, all screened in the same
session and found to explicitly block Claude by name.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://gulfnews.com/<section>/<slug>-1.<id>`

Multiple standalone `application/ld+json` script tags are present per
article (`BreadcrumbList` always; `Article` and/or `LiveBlogPosting` on
live-updating world-news stories) -- the extractor scans all of them and
picks the one with `"@type": "NewsArticle"`, which is always present
regardless of the other node types. That node **includes `articleBody`
directly** (full text -- verified 4-13 KB across 3 sampled articles,
including one live-updating piece), `author` as a **list** of
`{"@type": "Person", "name": ...}` (Gulf News frequently credits multiple
bylines/wire contributors on one story -- joined with `", "`), and
optional `description`/`keywords` (present on some articles, absent on
others -- read with `.get()`, no assumption either is always populated).

**Quirk:** `articleBody` (and occasionally `headline`/`description`)
contains **literal un-decoded HTML entities inline** -- `&nbsp;` confirmed
in samples (e.g. `"...at speeds up to 185 mph (298 km/h).&nbsp;."`). This
is NOT a JSON-escaping issue (`json.loads` already handles standard JSON
string escapes correctly) -- the CMS embeds real HTML entities directly
into the text value that ends up in the ld+json field. A second
`html.unescape()` pass on `headline`/`description`/`articleBody` cleans
this up.

No `isAccessibleForFree` field or other paywall marker was found in any of
the 3 sampled `NewsArticle` nodes.

### 2. Latest headlines — `S2-sitemap`

`GET https://gulfnews.com/news_sitemap.xml`

Google News sitemap, explicitly advertised via `Sitemap:` directive in
`robots.txt`. Standard fields (`news:title`, `news:publication_date`,
`news:keywords` comma-separated) plus `image:image` blocks (multiple
images per article, inline + lead) -- the extractor takes the **first**
`image:loc` found as a representative thumbnail (order in the sitemap
appears to put the lead/hero image first on sampled entries, though this
wasn't verified as a documented guarantee upstream).

## Paywall behavior

None observed. No `isAccessibleForFree` field, no paywall overlay markup,
and full `articleBody` text present and untruncated on all 3 sampled
articles (hard-news world/politics, sport, and a live-updating story).

## Known limits

- `news:keywords` on one sampled sitemap entry was a single long
  space-separated string rather than genuinely comma-separated tags (e.g.
  `"wyndham clark bmw championship mcilroy cantlay woodland"` as ONE
  keyword after comma-splitting, since the underlying string itself had no
  commas) -- this is passed through as-is via the same comma-split logic
  used elsewhere in the portfolio (e.g. `detik-scraper`); no special-casing
  added since it doesn't break anything, just yields a list with one long
  entry instead of several short ones for that particular article.
- Only 3 articles sampled in depth (1 live-updating world-news piece, 1
  sport, 1 politics/world). If a different section's `NewsArticle` node
  omits `articleBody` (e.g. a picture gallery or video-only page),
  `UnexpectedShape` will raise rather than silently returning nothing.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check the `&nbsp;`
un-decoded-entity quirk -- if Gulf News's CMS ever fixes this upstream, the
`html.unescape()` call becomes a harmless no-op rather than a needed fix.
