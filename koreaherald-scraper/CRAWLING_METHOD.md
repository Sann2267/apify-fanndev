# Crawling Method — Korea Herald

**Last verified:** 2026-08-24

## WAF

`koreaherald.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the latest-articles
sitemap -- no challenge body, no 403.

`robots.txt` is a minimal 5-line file (`Allow: /`, disallows a few internal
CMS paths like `/_TP/`, `/_CP/`, `/search`) -- **no Claude/GPTBot/
anthropic-ai disallow of any kind**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.koreaherald.com/article/<id>`

The `NewsArticle` ld+json block here is unusually **minimal** compared to
the rest of this portfolio -- only `headline`, `image`, `datePublished`/
`dateModified`, `author`, `publisher`. **No `articleBody`, no
`description`, no `keywords`.** The extractor therefore pulls from
multiple places:

- `headline`/`description` come from `<meta property="og:title">` /
  `<meta name="description">` instead of ld+json -- the ld+json
  `headline` has an unwanted `" - The Korea Herald"` site-name suffix
  baked in (e.g. `"...- The Korea Herald"`), while the meta tags carry the
  clean title.
- `datePublished`/`dateModified`/`author`/`image` still come from ld+json
  (these fields were accurate and suffix-free in all 3 samples).
- **Body text** comes from `<div itemprop="articleBody">` -- a
  schema.org microdata attribute (not ld+json), found via direct
  BeautifulSoup attribute lookup. Every `<p>` tag inside it is joined,
  **except** empty `<p class="newline">` spacer tags the CMS inserts
  between paragraphs purely for layout -- these have zero text content
  and are dropped by the same `if p.get_text(strip=True)` filter used
  everywhere else in this portfolio.

No `isAccessibleForFree` field or other paywall marker was found in any of
3 sampled articles (news brief, culture/festival piece, and a long-form
celebrity interview with 34 paragraphs) -- appears fully open-access.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.koreaherald.com/sitemap/latest-articles`

A rolling "latest articles" sitemap (distinct from the yearly archive
sitemaps also listed in `robots.txt`, e.g. `/sitemap/articles/2026`) --
continuously refreshed, ~73 entries at time of writing. Minimal shape:
`news:title` + `news:publication_date` per `<url>`, no image blocks.

**Quirk:** `news:title` is wrapped in a `<![CDATA[...]]>` block AND is
itself HTML-entity-escaped inside that CDATA (e.g.
`Kazakhstan&apos;s ruling party wins parliamentary elections: exit
polls`). Entities inside CDATA are **not XML-decoded** by the parser --
this is correct per the XML spec, not a bug -- so a literal `&apos;`
would leak into the output without a manual `html.unescape()` pass.
Same underlying issue (and same fix) as `independent-scraper`'s
`image:loc` CDATA quirk.

## Paywall behavior

None observed anywhere in this recon.

## Known limits

- Only 3 articles sampled in depth (news brief, culture, long-form
  interview). If a different content type (e.g. photo gallery, video
  page) lacks the `itemprop=articleBody` div, `UnexpectedShape` will raise
  rather than silently returning nothing.
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  ID) -- no soft-404 behavior observed.

## Diff cadence

Quarterly smoke test recommended.
