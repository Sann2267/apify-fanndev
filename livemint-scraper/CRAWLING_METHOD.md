# Crawling Method — Livemint

**Last verified:** 2026-08-24

## WAF

None detected. `www.livemint.com` returns 200 on homepage, article pages, and
the RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

Site is served by Next.js (`x-powered-by: Next.js` header present), but
article data is not in `__NEXT_DATA__` — it lives in JSON-LD, which is the
extraction target instead.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.livemint.com/<section>/<slug>-<id>.html`

Each article page emits **five separate** `application/ld+json` script tags:
`BreadcrumbList`, `NewsArticle`, `WebPage`, `NewsMediaOrganization`, and
`SiteNavigationElement` — the extractor picks out the `NewsArticle` one
specifically (same picking logic as `economictimes-scraper` and
`businessinsider-scraper`, reused as-is). The `NewsArticle` block is
unusually complete: `articleBody` contains the **full plain-text article**
(confirmed ~6000 chars on a full-length piece), plus `headline`,
`alternativeHeadline`, `description`, `datePublished`/`dateModified`,
`author`, `publisher`, `image`, `keywords`, and `mentions`.

### 2. Latest headlines — `S2-rss`

`GET https://www.livemint.com/rss/news`

Standard RSS 2.0 (`<channel>/<item>`) with CDATA-wrapped fields: `title`,
`link`, `guid`, `pubDate`, `description`, plus a `media:content` element
carrying the lead image URL (parsed into an `imageUrl` field — no other
built actor in this portfolio exposes a feed-level image, this is unique to
Livemint's feed). Feed content was confirmed chronological (items dated
within minutes of the request at recon time), unlike Economic Times'
`rssfeedsdefault.cms` which mixes in old evergreen items.

Other feed paths tried during recon and rejected: `/rss.xml` → HTTP 410
(gone), `/rssfeed` and `/feeds/rss` → HTTP 404 (site's default 404 page,
`text/html`). `/rss/homepage` returns 200 but is an HTML page, not a feed —
only `/rss/news` returns proper `application/xml`.

## Paywall behavior

No paywall encountered on the articles tested. Livemint's main news content
is free-to-read; a "Mint Premium" subscription tier exists for some content
but was not specifically hit during recon — per raw-passthrough convention,
if a premium article truncates `articleBody`, that truncation is passed
through verbatim rather than worked around.

## Known limits

- No confirmation yet that **every** section of the site (e.g. long-form
  opinion/analysis under `/opinion/`) uses the same 5-block ld+json shape as
  the market-news article tested — the extractor's `UnexpectedShape`
  exception will surface a genuine mismatch if one exists, no silent
  degrade.
- `/rss/news` is a single combined feed (not per-section) — same tradeoff as
  Economic Times' default feed, chosen for feed stability over topical
  filtering.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Livemint redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
