# Crawling Method — Free Press Kashmir

**Last verified:** 2026-08-26

Free Press Kashmir (`freepresskashmir.news`) is a regional/independent
Indian news outlet covering Jammu & Kashmir. This build is a purely
technical scraping task against publicly-published news content, same as
any other outlet in this portfolio.

Note: this is **not related to** Free Press Journal (`freepressjournal.com`,
Mumbai-based, already covered by this portfolio's `freepressjournal-scraper`)
-- separate publisher, separate region, similar name only by coincidence.

## robots.txt

`https://freepresskashmir.news/robots.txt` returns HTTP 200 with a body of
just a UTF-8 BOM + a single newline (`Content-Length: 4`) -- effectively
**empty**. No `User-agent`/`Disallow`/`Allow` directives of any kind, no
`Sitemap:` line, and (per the post-"Babak 17" screening requirement) **no
plain-English comment anywhere prohibiting AI/LLM training or scraping** --
there's nothing in the file at all beyond the BOM. No blanket `Disallow: /`,
no Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai block.
Independently re-verified with a fresh `curl_cffi` `chrome124` fetch during
this build (`GET https://freepresskashmir.news/robots.txt` -> HTTP 200, body
`﻿\n`) -- confirmed crawlable on both the machine-readable and
natural-language checks.

## WAF

`freepresskashmir.news` is fronted by **Cloudflare** (`server: cloudflare`,
`cf-ray`/`cf-cache-status` present) but presented **no challenge** to plain
`curl_cffi` `chrome124` impersonation during recon: homepage, `robots.txt`,
`sitemap.xml`/`post-sitemap.xml`, `/feed/`, and 3 article pages (a news
brief, a long-form feature, and a deliberately-invented slug) all returned
clean 200/404 with full content -- no "Just a moment"/`challenge-platform`/
captcha body markers, no unexpected 403/429/503.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://freepresskashmir.news/<yyyy>/<mm>/<dd>/<slug>/`

The site runs **WordPress + All in One SEO (AIOSEO) v4.9.9**, not Yoast.
Each article page emits **one** `<script type="application/ld+json"
class="aioseo-schema">` block -- an AIOSEO-style `@graph` array of 6
cross-referenced nodes: `Article`, `BreadcrumbList`, `Organization`,
`Person`, `WebPage`, `WebSite`.

The `Article` node carries `headline`/`name` (duplicated), `datePublished`,
`dateModified`, `articleSection` (a single comma-separated string mixing
categories AND tags, e.g. `"Health, In Depth, Special Report, cancer
patients Kashmir, cancer treatment delays, ..."` -- not a clean category, and
not an array), `image` (a single inline `ImageObject`) -- but **no
`articleBody`** on any of the 3 samples checked (a news brief, a long-form
feature, and re-confirmed on a second news brief).

**Both `author` and `publisher` on the `Article` node are ALWAYS bare
`{"@id": ...}` references**, never inlined -- unlike Guardian Nigeria (author
is a list of fully inline `Person` objects) but similar in mechanics to that
site's bare-ref `publisher`. Here:
- `author` resolves against the graph's own `Person` node. This is **not
  always a "News Desk" desk credit** -- one sample (`kashmirs-cancer-care-
  chapter-2-the-waiting-ward`) resolved to a named reporter, `"Al-Misda
  Masoom"`, with her own `/author/misda/` archive page and Gravatar image.
- `publisher` resolves against the graph's own `Organization` node
  (`name: "Free Press Kashmir"`). A `<meta property="og:site_name">`
  fallback exists in code but was never needed on any sample.

`html.unescape()` is applied to every text value pulled from the graph for
robustness, though no double-HTML-escaping quirk was observed on any of the
3 samples checked.

Full body text comes from HTML: **`div#content-main`, direct-child `<p>`
tags only** (`recursive=False`). Confirmed this exact `id` appears exactly
once per article page. Ad-slot `<div>` containers with randomly-generated
class names (e.g. `<div class="4oTiLlAw">`, wrapping AdSense
`<script async src="https://pagead2.googlesyndication.com/...">` tags and,
on some articles, a `div.fpkdonate` donation-nudge banner) sit as
direct-child `<div>` siblings interleaved between the `<p>` tags inside the
same container -- they're skipped automatically by the tag-name filter, no
extra scoping needed. The closing `div.mvp-related-posts` block (theme is
built on the "MVP"/MH-Magazine WordPress framework, confirmed by this class
name) also sits as a direct-child `<div>` sibling after the last `<p>` and is
skipped the same way. Body length across the 2 samples checked: 1,900-5,600
characters (news brief vs. long-form investigative feature).

`description` is pulled from `<meta name="description">`, falling back to
the ld+json `WebPage` node's own `description` field if the meta tag is ever
missing (not observed missing on any sample).

**404 handling:** a deliberately-invented slug
(`.../this-slug-definitely-does-not-exist-abc123xyz/`) returned a **real
HTTP 404** -- no soft-404 quirk observed.

**Non-article pages:** not directly sampled (e.g. `/about-us/`), but the
extractor explicitly detects a graph with no `Article`/`NewsArticle` node
and raises `ArticleNotFound` -> `_error: "not_article"` rather than crashing
on a schema-drift, matching the pattern used across this portfolio's other
WordPress-`@graph` actors.

### 2. Latest headlines — `S2-rss`

`GET https://freepresskashmir.news/feed/`

Standard WordPress RSS 2.0 feed (`<channel>/<item>`), confirmed live and
newest-first across 5 samples on 2026-08-26 (article timestamps
strictly descending, matching the site-wide `post-sitemap.xml`'s
`lastmod` ordering). Fields: `title`, `link`, `guid`, `pubDate`,
`description` (an HTML fragment -- a lead-image `<img>` tag plus a truncated
`<p>` teaser, raw-passthrough, not stripped), `dc:creator` (byline, resolves
via BeautifulSoup's namespace-stripping to `item.find("creator")`), and one
or more `<category>` tags per item (only the first is surfaced as
`category`; the rest are dropped since RSS 2.0 allows arbitrarily many
repeated elements and this portfolio's envelope expects a single value).

An `All in One SEO`-generated `post-sitemap.xml` (referenced from
`/sitemap.xml`, an AIOSEO sitemap index) was also confirmed live with 1,000
`<url>` entries carrying `loc`/`lastmod` (real per-article timestamps,
newest-first) but **no title** -- the RSS feed was chosen instead since it
carries a ready-to-use title in one lightweight request, avoiding a second
per-URL fetch just to get a headline.

## Paywall behavior

None observed on any of the 3 sampled articles. A `div.fpkdonate`
donation-nudge banner appears mid-article on at least one sample (a
"support independent journalism" call-to-action, common on non-profit/
independent outlets) -- this is a donation ask, not a content paywall; it
sits as its own `<div>` sibling and does not truncate or gate
`articleBody`, and is excluded from the extracted body automatically by the
`<p>`-only tag filter.

## Known limits

- Only 3 articles sampled in depth (2 news briefs + 1 long-form investigative
  feature, plus one invented-slug 404 probe). A structurally different
  template (e.g. a photo-gallery, video feature, or opinion/op-ed page) was
  not sampled.
- `articleSection` mixes categories and tags into one comma-separated string
  as authored by AIOSEO -- passed through as-is, not split or normalized.
- `latest` mode's RSS `category` field only captures the first `<category>`
  tag per item; additional categories/tags on the same item are dropped
  (article-mode's `articleSection` from JSON-LD is the fuller list).
- `description` in latest mode is an HTML fragment (embedded `<img>` +
  truncated `<p>`), not plain text -- raw passthrough of the feed's native
  shape, not cleaned.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `Article` ld+json node and `div#content-main`
still resolve. If Free Press Kashmir redesigns the page or switches SEO
plugins, `extract_article` will raise `UnexpectedShape` and the run will
fail loudly rather than emit corrupt records.
