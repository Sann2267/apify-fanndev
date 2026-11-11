# Crawling Method — Detik (detikNews)

**Last verified:** 2026-08-24

## WAF

`news.detik.com` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on homepage, article pages, and the news sitemap -- no
challenge body, no 403.

`robots.txt` (checked at the `news.detik.com` root) ends with
`User-agent: *` / `Allow: /` -- fully open, no Claude/GPTBot/anthropic-ai
disallow anywhere in the file.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://news.detik.com/berita/d-<id>/<slug>`

Detik emits **3 separate `application/ld+json` blocks** per article
(`BreadcrumbList`, `WebPage`, `NewsArticle`) -- the extractor scans all
script tags and picks the one with `"@type": "NewsArticle"`. That node
carries `headline`, `description` (a real teaser/summary, not a truncated
body), `datePublished`, `dateModified`, `author` (`{"@type": "person"}` --
note **lowercase** `"person"`, not `"Person"` like most schema.org
producers; harmless since the extractor only reads `.name`), `image`, and
`publisher`. **No `articleBody` field.**

Full text lives in HTML: `div.detail__body-text` (this element also
carries a second class, `itp_bodycontent` -- either selector works, `.
detail__body-text` was used since it's the more semantically obvious one).
Body paragraphs are bare `<p>` tags, but **one quirk requires filtering**:
an inline ad placeholder is interspersed mid-article as
`<p class="para_caption">SCROLL TO CONTINUE WITH CONTENT</p>` -- this is a
literal ad-slot label injected by Detik's own template (not a scraping
artifact), and must be excluded by its `para_caption` class rather than by
matching the English text (a class-based exclusion survives if the label
text is ever changed/localized). Several genuinely empty `<p>` tags
(spacing artifacts) also appear and are skipped via the truthy-text check.

### 2. Latest headlines — `S2-sitemap`

`GET https://news.detik.com/berita/sitemap_news.xml`

Detik's root `/sitemap.xml` is a **sitemap index** listing dozens of
per-channel sitemaps (`suara-pembaca`, `berita`, `internasional`,
`bbc-world`, `abc-australia`, `dw`, ...) each split into `sitemap_web.xml`
(all pages) and `sitemap_news.xml` (Google News format, recent articles
only). This actor targets `/berita/sitemap_news.xml` specifically -- the
main "detikNews" channel, the site's primary hard-news feed. Standard
Google News sitemap fields: `news:title`, `news:publication_date` (UTC,
`+00:00`), `news:keywords` (comma-separated), `loc` (all CDATA-wrapped,
unwrapped transparently by the XML parser).

## Paywall behavior

None observed. Detik is free, ad-supported (the `para_caption` ad
placeholder noted above being the main on-page monetization signal in the
article body itself) -- no subscription product or truncation marker
exists in the JSON-LD vocabulary or sampled HTML.

## Known limits

- Only 2 articles sampled (both hard-news, from the `berita` channel). If a
  different Detik vertical (e.g. `detikfinance`, `detikhealth`, `detikhot`)
  uses a different body-container class, this extractor would raise
  `UnexpectedShape` rather than silently return nothing -- revisit if
  cross-vertical coverage is needed (this actor is scoped to `detikNews`/
  `berita` only, matching the sitemap chosen for `latest` mode).
- `author.@type` is lowercase `"person"` in the sampled JSON-LD, a minor
  schema.org non-conformance on Detik's part -- documented here so a future
  agent doesn't assume a parsing bug if they notice it.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check that the
`para_caption` ad-placeholder class is still the correct exclusion marker --
if Detik renames or restructures that ad slot, the literal ad-label text
could leak into `articleBody` as a false paragraph.
