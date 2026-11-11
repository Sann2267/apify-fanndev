# Crawling Method — TASS

**Last verified:** 2026-08-24

## WAF

`tass.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the RSS feed -- no challenge
body, no 403.

`robots.txt` only disallows `/search`, no Claude/GPTBot/anthropic-ai
disallow of any kind.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://tass.com/<section>/<id>`

The page emits **3 separate ld+json blocks**: an `Organization` block, a
`@graph` of `SiteNavigationElement` menu entries, and a `NewsArticle`
block -- the extractor scans all `<script type="application/ld+json">`
tags and picks the one whose `@type` is `NewsArticle`. That block carries
`headline`, `description`, `datePublished`, `dateModified`, and
`author`/`publisher` (both typed `Organization` with `name: "TASS"` --
wire-service bylines are agency-attributed, not individual) -- but **no
`articleBody`**.

Full text comes from `div.text-block > p` -- plain, unwrapped `<p>` tags
with no extra classes or nested widgets to filter, confirmed on both a
3-paragraph brief and a 4-paragraph story.

No paywall marker of any kind was found (state media, fully open-access).

### 2. Latest headlines — `S2-rss`

`GET https://tass.com/rss/v2.xml`

Standard RSS 2.0: `title`, `link`, `guid`, `pubDate`, `description`
(short teaser, not full article text), `category` (single section name).

## Paywall behavior

None observed. Russian state news agency, fully open-access.

## Known limits

- `description` in `latest` mode is a teaser, not the full article body
  -- use `article` mode against the `link` for full text.
- 404s are real HTTP 404s (verified with a synthetic out-of-range
  article ID) -- no soft-404 behavior observed.
- Only 2 articles sampled in depth (a short 3-paragraph FX-rate brief and
  a 4-paragraph political story). Both shared the exact same markup
  pattern. A structurally different article type (e.g. a live-blog or
  photo-gallery page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
