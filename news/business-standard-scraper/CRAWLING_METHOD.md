# Crawling Method — Business Standard

**Last verified:** 2026-08-24

## WAF

None detected. `www.business-standard.com` returns 200 on homepage, article
pages, and RSS feeds under `curl_cffi` `chrome124` impersonation
(`server: nginx`), no `cf-ray`/`x-datadome`/`_abck`/Fastly markers, no
challenge body. A homepage GET is done first for hygiene/consistency with
the rest of the portfolio, not because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

Site is served by Next.js (`x-powered-by: Next.js`), but article data lives
in JSON-LD, not `__NEXT_DATA__`.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.business-standard.com/<section>/<slug>-<id>_1.html`

Each article page emits **five separate** `application/ld+json` script
tags: `NewsMediaOrganization`, `WebPage`, `SiteNavigationElement`,
`BreadcrumbList`, `NewsArticle` — the extractor picks out the `NewsArticle`
one specifically. `articleBody` is **full plain-text** for free articles
(confirmed ~4600 chars) but **truncated to a short teaser** (~380 chars,
ends mid-sentence) for paywalled articles — see Paywall behavior below.

### 2. Latest headlines — `S2-rss`

`GET https://www.business-standard.com/rss/latest.rss`

RSS 2.0 with **non-standard namespaced fields** beyond the usual
title/link/guid/pubDate/description:
- `dc:creator` — byline (mapped to `author`)
- `bs:premium` — `"true"`/`"false"` paywall flag (mapped to boolean
  `isPremium` — very useful for filtering out paywalled links *before*
  spending a request on them)
- `bs:keywords` — comma-separated tag string
- `media:content` (full image) / nested `media:thumbnail` — mapped to
  `imageUrl` / `thumbnailUrl`

Confirmed chronological and live (`lastBuildDate` matched request time at
recon). This is the named, documented site-wide feed — **do not** guess
numeric-ID feed paths like `/rss/latest-news-176.rss`; that pattern looks
plausible but actually hit a stale, unrelated "Bs Motoring" feed frozen
since 2023. The correct feed inventory was found by fetching
`/rss/home-page.rss` (an HTML directory page listing every section feed,
despite the `.rss` extension) and reading the linked `<a href>` URLs out of
it — `/rss/latest.rss` is the one labeled "Latest News".

## Paywall behavior

**Soft paywall, confirmed via recon.** Articles flagged `bs:premium=true` in
the RSS feed have their JSON-LD `articleBody` truncated to a short teaser
(one paragraph, ends mid-sentence, no truncation marker) rather than the
full body — same tier as `washingtonpost-scraper`/`ft-scraper` already in
this portfolio. Per raw-passthrough convention this actor does **not**
attempt to bypass it; the teaser is passed through verbatim, same as any
other field. Downstream consumers can pre-filter using the RSS feed's
`isPremium` flag if they only want free-to-read articles.

## Known limits / gotchas

- **Soft-404, not a real 404.** A nonexistent article URL returns
  **HTTP 200**, not 404 — the page still renders a `NewsArticle` ld+json
  block, but a blank placeholder one: no `headline`, no `articleBody`,
  and `url`/`mainEntityOfPage` literally end in the string `"comundefined"`
  (a client-side rendering artifact on their own error page). Relying on
  HTTP status alone would have silently emitted a garbage "article" record
  with `description: "Business Standard"` and empty fields. Fixed by
  `extractor.ArticleNotFound`: any matched `NewsArticle` block missing both
  `headline` and `articleBody` is treated as not-found and raises
  `ArticleNotFound`, which `main.py`/`test_local.py` catch and convert to
  the same `_error: "not_found"` record a real 404 would produce. This is
  the single most important thing to know before touching this actor's
  extractor — see `extractor._is_soft_404`.
- `/rss/latest.rss` is a single combined feed (not per-section) — same
  tradeoff as Economic Times/Livemint's default feeds, chosen for stability
  over topical filtering. Dozens of per-section feeds exist
  (`markets-106.rss`, `cricket-218.rss`, `industry/auto-21701.rss`, etc.)
  discoverable via `/rss/home-page.rss` if a future actor variant needs
  section filtering.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
free article URL and confirm `articleBody` is still full-length, and against
a known-bad URL to confirm the soft-404 detector still fires. If Business
Standard redesigns the page, `extract_article` will raise `UnexpectedShape`
(if the ld+json block disappears entirely) and the run will fail loudly
rather than emit corrupt records.
