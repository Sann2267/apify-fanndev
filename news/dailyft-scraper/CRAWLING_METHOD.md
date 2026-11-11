# Crawling Method — Daily FT

**Last verified:** 2026-08-25

## WAF

`ft.lk` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on the homepage, article pages, and the RSS feed. `robots.txt`
is fully open (`Allow: /` for `User-agent: *`, `Googlebot`, `Slurp`,
`msnbot`), no Claude/GPTBot/anthropic-ai disallow of any kind.

**Reliability quirk (not a block):** the backend (nginx behind
Cloudflare) returns intermittent 503 "Service Temporarily Unavailable" on
some endpoints, including the sitemap index -- confirmed transient by
retrying the exact same request seconds later and getting a clean 200.
This matches what earlier recon passes on this project logged as
"timeout" -- it's server flakiness, not an anti-bot signal. The existing
retry/backoff in `client.py` (status 503 is already in the retry set)
handles it without any special-casing.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Why this was previously flagged as hard (and how it was resolved)

This site was flagged across three prior recon sessions (Babak 11-13) as
"legacy markup, no ld+json, body container unclear" and left unbuilt.
This pass confirmed the diagnosis and found a working extraction path:

- **No ld+json anywhere** on article pages -- confirmed absent on every
  sampled template.
- The page carries `ng-app="single_module"` (AngularJS) and a
  `ng-controller="HitsController"` div, which initially looked like the
  whole article might be client-side rendered. **This turned out to be a
  red herring**: that Angular controller only powers a page-view "Hits"
  counter widget (`{{hitsCtrl.values.hits}}` visible unrendered in the
  raw HTML, next to the comment count) -- the actual article body is
  fully present in the server-rendered HTML, just under an
  inconsistently-formatted legacy template.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.ft.lk/<section>/<slug>/<categoryId>-<articleId>`

All fields are pulled from plain HTML/meta tags, since there's no
ld+json:
- `headline` <- `h1.innerheader`
- `deck` <- `header.inner-content > ul > li` (a one-line subheading --
  present on hard-news articles, confirmed **absent** on the opinion/
  column template; optional field, `null` when missing)
- `description` <- `meta[property=og:description]`
- `datePublished`/`dateModified` <- `meta[itemprop=datePublished]` /
  `meta[itemprop=dateModified]` (the only itemprop microdata this CMS
  emits anywhere -- no headline/author microdata)

**Two different hand-formatted body layouts were found**, both inside
`header.inner-content`, with no shared structural pattern:
- Hard-news template: a `<ul><li>` deck, an `<hr/>`, a `<table>` wrapping
  a pull-image + caption (decomposed/removed -- confirmed not body
  content), then a single large `<p>` whose paragraphs are separated by
  `<br/><br/>` rather than separate `<p>` tags.
- Opinion/column template: multiple real `<p>` tags (a styled pull-quote
  paragraph, an inline image + lead paragraph, then a further `<p>` whose
  own paragraphs are ALSO `<br/><br/>`-separated).

The extractor handles both without template-specific branches: decompose
any `<table>` inside the container, then for **every** `<p>` tag found
(recursively), split its inner HTML on runs of `<br>` tags and treat each
resulting fragment as one paragraph (after re-parsing the fragment to
strip any inline styling tags and collapsing `\xa0`/nbsp to a plain
space). This reconstructs full body text correctly on both sampled
templates.

**No author byline field was found** anywhere in metadata or near the
byline/date area on either sampled article -- `author` is intentionally
**omitted** from the output rather than guessed at. Note some article
bodies embed a byline as literal text at the start of the body/description
(e.g. `"By Charumini de Silva\r\n..."`, seen in one `latest`-mode sample)
-- that's part of the raw passthrough text, not a structured field.

### 2. Soft-404

A nonexistent article URL returns **HTTP 200** with `header.inner-content`
and `h1.innerheader` both absent, and `<title>` exactly matching the
homepage's own title string ("Sri Lanka's only national business
newspaper | Daily FT") -- confirmed on a synthetic out-of-range article
ID. Both conditions (title match AND missing h1) are required together
before the extractor treats it as `SoftNotFound` -- a future template
change that merely drops the h1 for some other reason on a *different*
page would still correctly raise `UnexpectedShape` instead of being
silently misclassified as "not found".

### 3. Latest headlines — `S2-rss`

`GET https://www.ft.lk/rss/top-story/26`

`/rss` itself is an HTML index page (not a feed) linking to several
per-section RSS 2.0 feeds (`/rss/news/3`, `/rss/columns/4`,
`/rss/opinion/14`, `/rss/sport/23`, etc.) -- `top-story` was picked
because its own feed `<description>` advertises "round the clock news
updates" and its content during recon spanned multiple sections (tourism,
politics, tax policy, court challenges), not one narrow category.
Confirmed fresh: newest feed item was newer than the article fetched
minutes earlier during recon.

**`pubDate` uses a non-standard format** (`"Monday, 24 August 2026
06:28"`, not RFC 822) -- passed through as the raw site string rather
than reformatted, per raw-passthrough convention.

**The site's own sitemap index (`/sitemaps`, advertised in `robots.txt`,
294 paginated files) was deliberately NOT used for `latest` mode**: the
highest-numbered file (`english-293000`) was found to lag real content by
roughly two months (newest entries dated December 2024 against articles
already live with IDs far beyond what that file covered) -- unreliable as
a "latest" source even though it's real, non-blocked data.

## Paywall behavior

None observed. Fully open-access on all sampled articles.

## Known limits

- Only 2 article templates sampled in depth (hard-news, opinion/column).
  A structurally different page type (live-blog, photo gallery, video)
  was not sampled and might not have a `header.inner-content` container
  at all -- would raise `UnexpectedShape` rather than silently emit a
  wrong or empty record.
- No structured `author` field exists on this CMS -- omitted rather than
  fabricated; some articles carry a byline as plain text inside the body.
- The backend occasionally returns 503 under load -- already handled by
  the standard retry/backoff, but a run against many URLs in one batch
  may be slower than usual if the backend is degraded.

## Diff cadence

Quarterly smoke test recommended.
