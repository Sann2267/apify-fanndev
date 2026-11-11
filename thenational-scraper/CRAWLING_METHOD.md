# Crawling Method — The National (UAE)

**Last verified:** 2026-08-24

## WAF

`thenationalnews.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the Arc outbound news
sitemap -- no challenge body, no 403.

`robots.txt` only restricts `Googlebot-Image` from certain image resizer
paths and disallows generic internal paths (`/search`, `/signin`,
`/personalization`, etc.) -- **no Claude/GPTBot/anthropic-ai disallow of
any kind**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.thenationalnews.com/<section>/<subsection>/<yyyy>/<mm>/<dd>/<slug>/`

The National runs on **Arc Publishing** -- the same CMS family as
`washingtonpost-scraper` (both ultimately under Nash Holdings). 3 standalone
`application/ld+json` script tags are present per article (`Organization`,
`NewsArticle`, `BreadcrumbList`) -- the extractor scans all of them and
picks the `NewsArticle` node, which **includes `articleBody` directly**
(verified 1.8-3.9 KB across 3 sampled articles: US news, UAE news, sport).

**Quirk specific to this CMS instance:** unlike every other Arc/JSON-LD
portfolio actor, `articleBody` is **not wrapped in `<p>` tags at all** --
it's one flat string with occasional inline `<a>` anchor tags (links to
related National articles embedded mid-sentence) and paragraph breaks
flattened to plain literal double-spaces (`"...backdrop.  The Freedom 250..."`).
The extractor therefore does NOT use `find_all("p")` (that would return
zero results and silently produce an empty body) -- it parses with
BeautifulSoup and calls `.get_text()` directly on the whole body, which
correctly drops the `<a>` tag markup while keeping the link text inline.
Body text also contains stray zero-width Unicode characters (`​`,
`‌`, `⁠`) inserted mid-word by the CMS -- passed through as-is,
not stripped (cosmetically invisible, doesn't break parsing or JSON
encoding).

`author` is always a **list** of `Person` dicts -- sometimes a single
`{"name": "The National"}` entry for staff/wire copy, sometimes a named
byline with a nested `image` field (author headshot, not the article's lead
image) -- names joined with `", "`.

**No paywall observed.** No `isAccessibleForFree` field or any other
metering marker in any of 3 sampled articles.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.thenationalnews.com/arc/outboundfeeds/news-sitemap/?outputType=xml`

Arc Publishing's outbound news sitemap, advertised via `Sitemap:` directive
in `robots.txt` (several other Arc sitemap variants also listed --
`sitemap-index`, `video-sitemap`, and 14 legacy `OldArticlesMissingSitemap`
paths for pre-migration content -- not used here, this one is the live
rolling news feed). Each `<url>` has `loc`, `lastmod`, a `news:news` block
(`news:title`, `news:publication_date`), and a single `image:image` block
(`image:loc` + `image:caption`) -- richer than `arabnews-scraper`'s
sitemap, comparable to `gulfnews-scraper`'s. 49 entries present at time of
writing.

## Paywall behavior

None observed anywhere in this recon.

## Known limits

- Only 3 articles sampled in depth (US news, UAE news, sport) plus 1
  editorial cartoon page (which also carries a full `NewsArticle` node with
  `articleBody`, so cartoon/opinion pages are not a special case). If a
  content type with genuinely absent `articleBody` exists (e.g. a live
  blog or video-only page), `UnexpectedShape` will raise rather than
  silently returning nothing.
- 404s are real HTTP 404s (verified with a synthetic slug) -- no soft-404
  behavior observed.
- `robots.txt` disallows the literal path `/article/` -- this does not
  affect this actor since all sampled article URLs use the
  `/<section>/<subsection>/<date>/<slug>/` pattern, never `/article/`.

## Diff cadence

Quarterly smoke test recommended.
