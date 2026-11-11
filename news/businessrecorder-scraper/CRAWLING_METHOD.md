# Crawling Method — Business Recorder

**Last verified:** 2026-08-25

## WAF

`brecorder.com` shows **no active challenge**. Cloudflare is present as CDN
only (`server: cloudflare`, `cf-ray` header on responses) but `curl_cffi`
`chrome124` gets a clean 200 with full content on the homepage, article
pages, `robots.txt`, and the sitemap -- no challenge body, no 403.

`robots.txt` has a single `User-agent: *` group disallowing only `*/print`,
`*/authors/*/<digit>*`, and `/search` -- no Claude/GPTBot/anthropic-ai
disallow of any kind.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.brecorder.com/news/<id>/<slug>`

The page emits 3 `<script type="application/ld+json">` blocks: an untyped
block, a `BreadcrumbList`, and a `NewsArticle` -- the extractor scans all
blocks and picks the one whose `@type` is `NewsArticle`. That block carries
`headline`, `description`, `datePublished`, `dateModified`, `author` (list
of `Person`), `publisher` (`Organization`), `image`, `url`,
`mainEntityOfPage`, and `copyrightYear` -- but **no `articleBody`**. The
whole ld+json block is passed through raw/verbatim (minimal renaming per
portfolio convention).

Full text comes from HTML `div.story__content > p` -- confirmed on
hard-news, markets, opinion, and analysis article types, with no ad/related-
article junk paragraphs mixed in.

**Quirk:** `description` (and occasionally `headline`) can contain raw HTML
entities (e.g. `&#039;` for an apostrophe) left un-decoded inside the
otherwise-plain-text ld+json field. Both are passed through
`html.unescape()` defensively before being emitted -- same pattern already
seen in `gulfnews-scraper` and `philstar-scraper`.

No paywall marker of any kind was found (fully open-access).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.brecorder.com/feeds/sitemap`

No RSS/Atom feed exists on this site -- `/rss`, `/rss.xml`, `/feed`,
`/feeds/rss`, and `/feeds/rss.xml` all return 404. This is a Google
News-flavored XML sitemap (declares the `news_sitemap.xsd` namespace,
discovered via the `Sitemap:` line in `robots.txt`) that lists the ~100
most recently published articles site-wide. Each `<url>` block carries a
nested `<news:news>` block with `news:title`, `news:language`, and
`news:publication_date` (date-only granularity, no time component).
Section/landing-page `<url>` entries (e.g. `/markets`, `/world`) share the
same sitemap but lack a `<news:news>` block, so the extractor skips any
`<url>` without one.

Sitemap order is not strictly chronological, so items are re-sorted by the
numeric article ID embedded in the URL (`/news/<id>/...`), descending, as a
more reliable "newest first" proxy than trusting document order.

## Paywall behavior

None observed across all sampled articles (hard-news, markets, opinion,
analysis) -- fully open-access financial daily.

## Known limits

- `publicationDate` in `latest` mode is date-only (no time-of-day), so
  same-day ordering relies entirely on the numeric-ID sort, not the date
  field itself.
- Real 404s confirmed via synthetic out-of-range article ID (returns a
  genuine HTTP 404 with "Not Found - Business Recorder" title) -- no
  soft-404 behavior observed.

## Diff cadence

Quarterly smoke test recommended.
