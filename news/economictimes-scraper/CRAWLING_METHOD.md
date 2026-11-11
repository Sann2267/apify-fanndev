# Crawling Method — Economic Times

**Last verified:** 2026-08-24

## WAF

None detected. `economictimes.indiatimes.com` returns 200 on homepage,
article pages, and RSS feeds under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://economictimes.indiatimes.com/<section>/<slug>/articleshow/<id>.cms`

Each article page emits **three separate** `application/ld+json` script
tags: `NewsMediaOrganization`, `NewsArticle`, and `WebPage` — the extractor
picks out the `NewsArticle` one specifically (the other two are noise for
this actor's purpose). The `NewsArticle` block is unusually complete for a
JSON-LD implementation: it includes `articleBody` with the **full plain-text
article** (not just a teaser), plus `headline`, `description`, `keywords`,
`inLanguage`, `datePublished`/`dateModified`, and `articleSection`. No
`__NEXT_DATA__` or other SSR data container was found — this site is not
built on Next.js.

### 2. Latest headlines — `S2-rss`

`GET https://economictimes.indiatimes.com/rssfeedsdefault.cms`

Standard RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`, `guid`,
`pubDate`, `description`. No byline/creator field present. **Note:** this
"default" feed is not strictly chronological — it mixes fresh items (top of
feed, matching current date) with occasional much older evergreen items
further down (confirmed 2026-08-24: some entries dated 2008-2014 appear
mixed in among 2026 items). Per-section feed IDs also exist at
`/rssfeeds/<numeric-id>.cms` (e.g. `1373380680.cms` for Economy), but section
IDs are undocumented and not guaranteed stable, so this actor standardizes on
the always-live default feed rather than hardcoding a section-ID list that
could rot.

## Paywall behavior

No paywall encountered on the articles tested. Economic Times' main news
content is free; a separate premium tier ("ET Prime") exists but was not
specifically tested here — if a Prime article truncates `articleBody`, that
truncation is passed through verbatim per the raw-passthrough convention,
this actor does not attempt to work around it.

## Known limits

- `latest` mode is not guaranteed strictly-recent-only; sort/filter by
  `pubDate` downstream if you need a strict time window.
- Some title/description text contains a zero-width space character
  (U+200B) as authored by Economic Times' CMS — passed through verbatim, not
  stripped, per raw-passthrough convention.
- No author/byline field is exposed in either the RSS feed or the JSON-LD
  block for the articles tested.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Economic Times redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
