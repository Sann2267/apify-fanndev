# Crawling Method — Korea Times

**Last verified:** 2026-08-24

## WAF

`koreatimes.co.kr` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the news sitemap -- no
challenge body, no 403.

`robots.txt` blocks a handful of generic scraping/AI-training bots
(`Bytespider`, `Amazonbot`, `DataForSeoBot`, `magpie-crawler`, `omgili`,
`peer39_crawler`, `Brightbot`) but has **no Claude/GPTBot/anthropic-ai
disallow of any kind**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.koreatimes.co.kr/<section>/<subsection?>/<yyyymmdd>/<slug>`

(Note: the site was recently redesigned to this date-in-path URL scheme --
older links using a numeric `/www/<id>.html` pattern seen in some external
references no longer resolve to live articles.)

A `NewsArticle` ld+json block (plus an unrelated `FAQPage` block present on
some pages, ignored) **includes `articleBody` directly** (verified 3.9 KB
on a sampled business article). `author` is always a **list** of `Person`
dicts, joined with `", "`. No `isAccessibleForFree` or other paywall
marker was found.

**Soft-404 handling (the important part of this recon):** an invalid or
removed article URL returns **HTTP 200**, not 404 -- served as a generic
section-listing page (`<title>` is just `"<Section> - The Korea Times"`,
**zero ld+json blocks of any kind**). Since "zero ld+json blocks" is
ambiguous on its own (could mean the URL is bogus, or could mean the site
changed its real-article markup), the extractor disambiguates using
`<link rel="canonical">`:

- **Real article:** canonical URL path == requested path exactly.
- **Soft-404:** canonical URL path is the **shorter section root**
  (e.g. requesting `.../business/companies/20260823/typo-slug`
  canonicalizes to `.../business/companies`, with the date+slug segments
  dropped entirely).

If no `NewsArticle` block is found AND the canonical path doesn't match
the requested path, it's `ArticleNotFound` (mapped to `_error: "not_found"`
in `main.py`, same as a real HTTP 404). If no block is found but the
canonical path *does* match, that's genuine `UnexpectedShape` -- the
upstream markup has changed in a way this extractor doesn't recognize, and
the run should fail loudly rather than silently miscategorize a shape
change as a missing article.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.koreatimes.co.kr/sitemap/news.xml`

Reached transitively: `robots.txt` -> `/sitemap/sitemap.xml` (a
sitemapindex with two entries: `sitemap-sections.xml` and
`sitemap-news.xml`) -> `sitemap-news.xml` turned out to be a **decoy**:
it's itself a sitemapindex pointing to `sitemap/news.xml` +
`sitemap/month.xml`, and resolving `sitemap-news.xml` directly (i.e.
treating it as a leaf `<urlset>`) returns **0 entries**. The real rolling
news feed is one level deeper, at `/sitemap/news.xml` (194 entries at time
of writing). `sitemap-sections.xml` is a separate index of per-category
archive sitemaps (`southkorea.xml`, `business.xml`, etc.) -- not used here,
since `/sitemap/news.xml` already covers the rolling cross-section feed.

Shape: `news:title` (site-name suffix `" - The Korea Times"` baked
directly into the value, unlike the clean `headline` on article pages --
passed through as-is), `news:publication_date`, `news:keywords`
(comma-separated), `lastmod`, one `image:image` block per entry.

## Paywall behavior

None observed anywhere in this recon.

## Known limits

- Only 1 article sampled in depth (a business/companies story). Other
  section types (opinion, entertainment/k-pop, sports) were spot-checked
  for the soft-404 canonical behavior but not for `articleBody` structural
  variance.
- The soft-404 disambiguation relies on `<link rel="canonical">` being
  present and accurate -- if a future redesign removes or misconfigures
  this tag, the fallback behavior (`_canonical_matches` returns `True`
  when no canonical tag exists) means a genuine soft-404 would incorrectly
  raise `UnexpectedShape` instead of `ArticleNotFound`. This is a
  deliberate fail-loud choice: better to surface an unexpected page shape
  than to silently swallow it as "not found."

## Diff cadence

Quarterly smoke test recommended, plus a spot-check of the soft-404
canonical-URL logic given the site's recent URL-scheme redesign (higher
chance of further changes in the near term).
