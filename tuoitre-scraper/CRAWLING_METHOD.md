# Crawling Method — Tuổi Trẻ News

**Last verified:** 2026-08-25

## WAF

`tuoitrenews.vn` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the RSS feed -- no
challenge body, no 403.

`robots.txt` is a single trivial group (`User-agent: *` / `Allow: /`), no
Claude/GPTBot/anthropic-ai disallow of any kind.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

**Quirk:** every request to `tuoitrenews.vn` (homepage, articles, `/rss`)
transparently 302-redirects to `news.tuoitre.vn` -- a dedicated
English-edition subdomain of `tuoitre.vn` (NOT the Vietnamese-language
main site, which was never screened/used). `news.tuoitre.vn`'s own
`robots.txt` was verified separately and is equally permissive
(`Allow: /`). Since `curl_cffi` follows redirects by default, feeding it
`tuoitrenews.vn` URLs "just works" -- links from `tuoitrenews.vn` pages
(including RSS `<link>` values) resolve directly to `news.tuoitre.vn`.

## Data sources

### 1. Article pages — `S1-html`

`GET https://tuoitrenews.vn/<slug>-<id>.htm` (redirects to
`news.tuoitre.vn/...`)

The page emits 3 ld+json blocks: a `NewsArticle`, a `BreadcrumbList`, and
an `Organization` -- the extractor scans all blocks and picks the one
whose `@type` is `NewsArticle`. That block carries `headline`,
`description`, `datePublished`, `dateModified`, `author` (a `Person` --
individual bylines, unlike wire-service outlets), and `publisher` (an
`Organization`) -- but **no `articleBody`**.

Full text comes from HTML `div.detail-content > p`, explicitly excluding
`<p>` tags nested inside `<figcaption>` (photo captions, would otherwise
pollute body text) and inside any `[relatednewsboxtype]` block
(related-articles widget -- has no `<p>` tags in practice, excluded
defensively anyway).

**Quirk:** HTML entities in ld+json string fields (e.g. `&#39;` in
headlines like "Ho Chi Minh City's...") are left un-decoded -- all
string fields (`headline`, `description`, `author`, `publisher`) are
passed through `html.unescape()` before being emitted.

No paywall marker of any kind was found.

### 2. Latest headlines — `S2-rss`

`GET https://tuoitrenews.vn/rss` (redirects to `news.tuoitre.vn/rss`)

Standard RSS 2.0: `title`, `link`, `description` (short teaser, not full
article text), `author`, `pubDate`, `enclosure` (image URL). Confirmed
**absent** on this feed across 50 sampled items: `guid` and `category` --
neither field exists, so the extractor doesn't attempt to read them.

## Paywall behavior

None observed. Fully open-access.

## Known limits

- `description` in `latest` mode is a teaser, not the full article body --
  use `article` mode against the `link` for full text.
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  slug, which returns a genuine 404 with a Vietnamese "Trang thông báo lỗi
  404" error page) -- no soft-404 behavior observed.
- RSS `link` values point at `news.tuoitre.vn`, not `tuoitrenews.vn` --
  both resolve to the same content, this is cosmetic only.

## Diff cadence

Quarterly smoke test recommended.
