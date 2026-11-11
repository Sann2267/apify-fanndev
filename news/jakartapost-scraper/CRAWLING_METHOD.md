# Crawling Method — The Jakarta Post

**Last verified:** 2026-08-24

## WAF

`thejakartapost.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the news sitemap -- no
challenge body, no 403.

`robots.txt` only blocks a handful of utility paths (`/wp-admin/`,
`/xmlrpc.php`, promo/survey pages) for `User-agent: *`, plus a blanket
`Disallow: /` for `GPTBot` specifically -- **no Claude/anthropic-ai
disallow**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.thejakartapost.com/<section>/<yyyy>/<mm>/<dd>/<slug>`

A single `NewsArticle` ld+json block carries `headline`, `datePublished`,
`dateModified`, `author` (list of `{"@type": "Person", "name": ...}`),
`image`, `publisher`, and **`isAccessibleForFree`** (string `"true"`/
`"false"`, not boolean). **It has no `articleBody` and no `description`
field** -- description is instead read from `meta[property="og:description"]`.

**Full text extraction requires the HTML**, and the page layout has one
genuine quirk: the first paragraph is split into
`div.tjp-opening > h1.tjp-opening__char` (a single drop-cap letter, e.g.
`"P"`) + `p.tjp-opening__txt` (the rest of the sentence, e.g.
`"olice have named..."`) -- these must be concatenated **with no
separating space** to reform the real word (`"Police have named..."`).
Subsequent paragraphs are bare `<p>` tags that are **direct children** of
`div.tjp-single__content` alongside ad (`div.tjp-single__content-ads`) and
newsletter-signup (`div.tjp-newsletter-box`) wrapper `<div>`s at the same
nesting level -- calling `.find_all("p", recursive=False)` on the container
naturally skips the `<p>` tags nested inside those wrapper divs (verified:
direct-child paragraph count matched the visible narrative paragraph count
exactly on 3 sampled articles, with ad/newsletter divs correctly excluded).

`div.tjp-single__content` is a **tight, well-bounded container** (~6-7 KB
per sampled article) that ends before the "Related Article" / "Popular" /
comment sections and before the `div.tjp-paywall` gate markup, so no
extra filtering of trailing sections is needed.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.thejakartapost.com/sitemap_news.xml`

Google News sitemap format (`news:title`, `news:publication_date`, `loc`),
continuously refreshed, listing all articles published recently (typically
the last 2 days). Not explicitly gated in `robots.txt` (multiple
`Sitemap:` directives are advertised there, including this one).

## Paywall behavior

**Soft/cosmetic paywall confirmed.** `isAccessibleForFree` was `"false"` on
every sampled article (including a hard-news wire piece and an opinion
column), and a `div.tjp-paywall` overlay ("to Read Full Story", subscribe
CTA starting at IDR 70,000/month) exists further down the page -- but the
**full `articleBody` text is always present in the raw server-rendered
HTML**, inside `div.tjp-single__content`, well before the paywall gate
markup begins. The gate is enforced client-side (JS overlay/CSS), same tier
as `latimes-scraper` / `chicagotribune-scraper`. The extractor sets
`_paywalled: true` (derived from `isAccessibleForFree == "false"`) so
downstream consumers can distinguish nominally-premium articles, but does
**not** truncate or omit `articleBody` -- no sampled article (3/3) showed
truncated text.

## Known limits

- Only 3 articles sampled (2 hard-news, 1 opinion column), all from the
  news sitemap. If The Jakarta Post ever moves to server-side truncation for
  premium content, this extractor would need a new signal -- the current
  `_paywalled` flag is informational only, not gate-detection.
- `div.tjp-opening` was present on all 3 samples; if a future article
  layout (e.g. live blog, picture gallery) omits it, the extractor still
  falls back to whatever direct `<p>` children exist in
  `.tjp-single__content` -- an article with truly zero body paragraphs would
  raise `UnexpectedShape` rather than emit an empty record.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check that
`div.tjp-single__content`'s direct-child structure (bare `<p>` interspersed
with ad/newsletter wrapper `<div>`s) hasn't changed -- a theme update that
wraps paragraphs in a new intermediate `<div>` would silently empty the
`recursive=False` extraction.
