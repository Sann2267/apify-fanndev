# Crawling Method — 20 Minutes

**Last verified:** 2026-08-24

## WAF

`20minutes.fr` is fronted by Cloudflare (`cf-ray` header present on every
response) but **no active challenge** was observed. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the site-wide RSS feed --
no `Just a moment`/challenge body, no 403.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.20minutes.fr/<section>/<id>-<date>-<slug>`

Each article page emits an `application/ld+json` block with `@type`
`NewsArticle` for regular articles. `articleBody` carries the **full
plain-text article** -- no paywall marker (`isAccessibleForFree`, etc.) was
found on any sampled article. 20 Minutes is a free, ad-supported daily
(the French equivalent of Metro/AM New York) with no subscription product,
which matches: nothing to gate.

**Quirk — live blogs use a different `@type`:** sports and breaking-news
"direct" pages (e.g. live match coverage) emit `@type: "LiveBlogPosting"`
instead of `NewsArticle`. It carries the same `articleBody` field (a short
top-line summary, e.g. `"Fils-Tiafoe 6-3, 1-6, 6-0"`) plus a `liveBlogUpdate`
array with the individual timestamped updates. Both types are recognized by
the extractor and passed through verbatim, undifferentiated in shape beyond
`@type`. If a consumer wants only static articles, filter on `@type` in the
output dataset.

No `__NEXT_DATA__` was found (0 ld+json articleBody truncation observed
across the NewsArticle + LiveBlogPosting samples tested).

### 2. Latest headlines — `S2-rss`

`GET https://www.20minutes.fr/feeds/rss-une.xml`

Standard RSS 2.0 front-page feed, 30 items per fetch. Beyond the usual
`title`/`link`/`guid`/`pubDate`/`description`, this feed uniquely carries:
- `<author>` -- plain-text byline (not a `dc:creator` namespace tag).
- `<body>` -- a CDATA block containing the **full article as raw HTML**
  (matches `articleBody` content, wrapped in `<p>`/`<figure>` tags) --
  passed through as-is in the `body` field, consistent with how
  `businessinsider-scraper` passes through its Atom feed's `content` field.
- `<category>` -- one or more per item (topic/tag), collected into
  `categories`.

## Paywall behavior

None observed. Full article text available via both JSON-LD (`articleBody`)
and the RSS `<body>` CDATA field.

## Known limits

- `LiveBlogPosting` articles only carry a short top-line `articleBody`
  summary in the JSON-LD, not full blow-by-blow commentary -- the
  `liveBlogUpdate` array (unstructured passthrough) has the individual
  updates if a consumer needs them.
- No section-specific RSS feeds were tested; only the site-wide "Une" (front
  page) feed is wired up.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
regular-article URL and a fresh live-blog URL (search the RSS feed for a
`/direct/` or "en direct" title) to confirm both `@type` variants still
parse cleanly.
