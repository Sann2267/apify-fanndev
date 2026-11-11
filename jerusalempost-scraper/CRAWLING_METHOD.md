# Crawling Method — Jerusalem Post

**Last verified:** 2026-08-25

## WAF

`jpost.com` (served via `www.jpost.com`) shows **no active challenge**.
`curl_cffi` `chrome124` gets a clean 200 on homepage (~750KB), article
pages, the Google News sitemap, and the sitemap index — no challenge body,
no 403.

`robots.txt` explicitly names AI agents and **allows** them:

```
User-agent: Claude-User
Allow: /
Disallow: /showimage.ashx*
Disallow: /premiumlogin/
Disallow: /servlet/
Disallow: /printarticle.aspx*
Disallow: /pdf/
Disallow: /directory/
Disallow: /search;query
Disallow: /comments/
Disallow: /test-ads/
Disallow: /insights/
```

(Same pattern repeated for `GPTBot`, `ChatGPT-User`, `OAI-SearchBot`,
`Perplexity-User`.) None of the disallowed paths are used by this actor.
Note: this is the *clean* sibling outlet — Haaretz (haaretz.com) explicitly
blocks Claude in its robots.txt; do not confuse the two.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.jpost.com/<section>/(<subsection>/)article-<id>`

The page emits **5 separate ld+json blocks**: `WebSite`,
`NewsMediaOrganization`, `NewsArticle`, `BreadcrumbList`, and one untyped
block — the extractor scans all `<script type="application/ld+json">` tags
and picks the one whose `@type` is `NewsArticle`.

Unlike TASS (the sibling reference actor), the `NewsArticle` block here
carries **`articleBody` inline, with full text** — no HTML fallback
selector was needed. It also carries `headline`, `description`,
`datePublished`, `dateModified`, `author` (a **list** of `Person` objects
— individual bylines, e.g. `"SUSAN HATTIS ROLEF"`, not agency-attributed
like TASS), `publisher` (`NewsMediaOrganization`, name `"The Jerusalem
Post"`), `image` (list of `ImageObject`), `articleSection`, `keywords`,
and `isAccessibleForFree` (boolean paywall flag).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.jpost.com/GoogleNewsSiteMap/GNSiteMap`

No RSS/Atom feed exists — `/rss` and `/RSS` return HTTP 200 but are
Next.js **HTML pages**, not feeds (`content-type: text/html`), and
`/rss.xml`, `/feed`, and other common feed paths all 404. Instead, `latest`
mode uses the **Google News sitemap** referenced in `robots.txt`
(`Sitemap: https://www.jpost.com/GoogleNewsSiteMap/GNSiteMap`), a standard
sitemap-news XML feed with ~300 recent articles (confirmed 311 entries at
recon time), each carrying `loc`, `lastmod`, `news:title`,
`news:publication_date`, and `news:keywords` (comma-separated) inline — no
per-article fetch needed. `robots.txt` also lists a full-archive
`sitemapindex.xml` under `/jpgooglesitemap/` (dozens of gzipped shards,
40k articles each) for potential future backfill/discovery use, but that's
overkill for "latest".

## Paywall behavior

`isAccessibleForFree` is a genuine field in the `NewsArticle` ld+json, and
the extractor honors it (`_paywalled` output flag) rather than assuming
the site is fully open. **13 diverse articles were sampled** during recon
across sections (`israel-news`, `opinion`, `sports`, `defense-and-tech`,
`archaeology`, `history`, `travel`, `food-recipes`, `omg`, `mdaheroes`,
`american-politics`, `israel-election-2026`) — all were
`isAccessibleForFree: true` with full-length `articleBody` matching the
displayed page. No paywalled sample was found, but the actor does not
crash if one is encountered: a `false` flag produces a `_paywalled: true`
record with whatever body text is present (short teaser or empty),
instead of raising `UnexpectedShape` or fabricating text. A genuinely
open article with an empty body IS treated as schema drift and raises.

## Known limits

- No paywalled article was found in the 13-sample recon set — the
  `_paywalled` handling path is implemented defensively but not exercised
  against a real paywalled example. If JPost Premium content shows up in
  practice, downstream consumers should check `_paywalled` before trusting
  `articleBody` completeness.
- `latest` mode is capped by whatever the Google News sitemap currently
  holds (~300 articles, most-recent-first was not strictly verified —
  entries were observed in roughly reverse-chronological order by
  `lastmod`).
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  ID: `/israel-news/article-999999999` → genuine Next.js 404 page, HTTP
  404) — no soft-404 behavior observed.
- `author` is a list because JPost bylines are individual reporters, not
  the agency (contrast with TASS where author/publisher are both always
  `"TASS"`). The extractor flattens to a list of names (or a single name
  if only one).

## Diff cadence

Quarterly smoke test recommended.
