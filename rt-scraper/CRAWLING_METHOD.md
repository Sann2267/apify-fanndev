# Crawling Method — RT

**Last verified:** 2026-08-24

## WAF

`rt.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the RSS feed -- no challenge
body, no 403.

`robots.txt` disallows a set of functional paths (`/search*`,
`/login*`, `/api/`, `/preview*`, `/*/video/`, query strings via `*?`,
etc.) for `Googlebot`, `bingbot`, and `*` -- **no Claude/GPTBot/
anthropic-ai disallow of any kind.** Article paths (`/news/<id>-<slug>/`)
are not disallowed.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.rt.com/<section>/<id>-<slug>/`

The page emits 3 ld+json blocks: `Organization`, `BreadcrumbList`, and
`NewsArticle` -- the extractor scans all `<script
type="application/ld+json">` tags and picks the one whose `@type` is
`NewsArticle`. That block carries `headline`, `description`, `image`
(array of `ImageObject`), `author`/`publisher` (both typed
`Organization`, name `"RT"` in every sample -- wire-style attribution,
not individual bylines even for opinion pieces), `datePublished`,
`dateModified` -- but **no `articleBody`**.

Full text comes from `div.article__text > p` -- plain `<p>` tags, no ad
slots, embeds, or "READ MORE" boxes found inside the container across a
21-paragraph opinion-piece sample.

No paywall marker of any kind was found (state-funded broadcaster,
fully open-access).

### 2. Latest headlines — `S2-rss`

`GET https://www.rt.com/rss/`

RSS 2.0 with two body-bearing elements per `<item>`:
- `<description>` -- a short teaser: raw HTML with an embedded `<img>`
  thumbnail, the teaser sentence, and a `<br/><a href="...">Read Full
  Article at RT.com</a>` link. Kept as raw unparsed HTML under `teaser`
  since it's not meant to be read as plain text.
- `<content:encoded>` -- **the full article body as HTML**, unusual for
  this portfolio (most other outlets' RSS feeds are teaser-only). Parsed
  identically to the article-page body: `<p>` tags extracted and joined
  with blank lines. This means `latest` mode alone is often sufficient
  without a follow-up `article`-mode call.

`<link>` carries `?utm_source=rss&utm_medium=rss&utm_campaign=RSS`
tracking params that are stripped before output (split on
`?utm_source=`) so the URL matches the canonical article-mode input
shape.

## Paywall behavior

None observed. State-funded broadcaster, fully open-access.

## Known limits

- `author`/`publisher` were `"RT"` (Organization) in every sample seen --
  a byline-attributed opinion piece with an individual author name in
  ld+json was not sampled and might have a different shape (this is
  common on RT for signed op-eds); the extractor still handles that case
  since it reads whatever `name` is present.
- 404s are real HTTP 404s (verified with a synthetic out-of-range
  article ID) -- no soft-404 behavior observed.
- Only 3 articles sampled in depth. All shared the exact same markup
  pattern. A structurally different article type (video page, live
  updates) was not sampled and is excluded by `robots.txt` for `/video/`
  paths anyway.

## Diff cadence

Quarterly smoke test recommended.
