# Crawling Method — The Tribune (India)

**Last verified:** 2026-08-27

The Tribune (`tribuneindia.com`) is a major North India English daily
newspaper based in Chandigarh.

## Robots.txt

```
User-agent: *
Allow: /
Sitemap: https://www.tribuneindia.com/sitemap.xml
Sitemap : https://www.tribuneindia.com/sitemap-news.xml
Sitemap : https://www.tribuneindia.com/recent-sitemap.xml
```

A minimal 4-line file: one `User-agent: *` group with an explicit
`Allow: /` and no `Disallow` directives at all, plus three `Sitemap:` lines.
No Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
block of any kind, only one user-agent group, and no natural-language
prohibition against AI/LLM training or scraping anywhere in the file.
Independently re-verified with a fresh `curl` fetch during this build
(`GET https://www.tribuneindia.com/robots.txt` -> HTTP 200, body as above,
grepped for `claude|anthropic|gptbot|ai|bot|crawl|disallow` — zero hits
beyond the boilerplate) — confirmed crawlable.

## WAF

None detected. `curl_cffi` `chrome124` returns a clean 200 on the homepage,
article pages, `/recent-sitemap.xml`, and `/sitemap-news.xml` on the first
try — `server: nginx`, no `cf-ray`/`x-datadome`/`_abck`/Fastly markers, no
challenge body. A homepage GET is done first for hygiene/consistency with
the rest of the portfolio, not because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

`/feed`, `/feed/`, `/rss.xml`, `/rssfeed.xml`, and `/news/rss.xml` all
return 403/404 — no RSS feed is exposed on this site (the 403 on `/feed` and
`/feed/` is a path-specific block, not a general fingerprint gap, since the
exact same profile 200s cleanly on the homepage, article pages, and both
sitemaps). `latest` mode uses `/recent-sitemap.xml` instead.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.tribuneindia.com/news/<section>/<slug>/`

Each article page emits **8** separate `<script type="application/ld+json">`
blocks: `NewsArticle`, `ProfilePage`, `WebPage`, `BreadcrumbList`, one that
fails `json.loads()` (a `SiteNavigationElement` block containing a raw
control character — harmless, silently skipped, never the block we need),
`WebSite`, `SiteNavigationElement`, `ViewAction`. `extract_article()` scans
all of them and picks out the one with `@type == "NewsArticle"`; it is a
**bare dict**, not wrapped in a Yoast-style `@graph` array.

The `NewsArticle` node already carries the full plain-text `articleBody`
(confirmed non-empty on every sampled article, 1,100–3,500+ characters) —
no HTML-body fallback is needed, unlike Guardian Nigeria in this portfolio.
It also carries `headline`, `description`, `keywords` (an **array**, unlike
Hindustan Times' comma-separated string), `articleSection`, `author` (a
**single `Person` dict**, not an array — usually a wire-service credit like
`"PTI"` or `"ANI"` rather than a staff byline), `publisher`
(`NewsMediaOrganization`), `image`/`thumbnailUrl`, `datePublished`/
`dateModified`, `isAccessibleForFree`, `sameAs` (the outlet's own social
links, not article-specific), `genre`, `inLanguage`, `speakable`,
`mainEntityOfPage`, `isPartOf`.

**Quirk 1:** `headline` carries a `" - The Tribune"` suffix (e.g.
`"...in Surat - The Tribune"`) baked in by the CMS as an SEO title-tail —
passed through verbatim per raw-passthrough convention, unlike Hindustan
Times' `" | <Section>"` pattern this is a plain hyphen separator.

**Quirk 2:** `keywords` is usually a real array of topic tags (confirmed on
2 of 3 sampled articles — hashtags and named-entity phrases), but on at
least one sampled article it was a single-item array that just duplicates
the `headline` text verbatim instead of real tags — a CMS quirk, passed
through as-is rather than normalized.

**Encoding note:** raw response bytes for apostrophes/quotes are correct
UTF-8 (`\xe2\x80\x99` = U+2019 RIGHT SINGLE QUOTATION MARK, confirmed via a
byte-level check). Any `�` seen when eyeballing output in a Windows terminal
is a **console codepage rendering artifact**, not real data corruption —
`json.dumps(..., ensure_ascii=False)` and downstream consumers reading the
UTF-8 bytes directly see the correct character.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.tribuneindia.com/recent-sitemap.xml`

Since no RSS feed is exposed (see WAF section), `latest` mode reads this
sitemap instead — confirmed live with exactly **100** `<url>` entries.
Each entry carries `<loc>`, `<lastmod>` (real per-article ISO 8601
timestamp), and `<image:image><image:title>` (used as the headline text,
since there's no dedicated `<news:title>` element on this sitemap). Not
confirmed strictly newest-first in file order — two adjacent entries were
observed out of chronological order during recon (a 22:33:01 entry
immediately followed by a 22:34:29 entry) — `extract_sitemap_items()` sorts
descending by `lastmod` defensively.

`/sitemap-news.xml` (the standard Google News sitemap, also referenced from
robots.txt) was also confirmed live — 1,214 entries, same `news:` schema as
other Yoast-style sitemaps in this portfolio (`news:title`,
`news:publication_date`) — but `/recent-sitemap.xml` was chosen as the
default since it's a tighter, purpose-built "most recent" feed (exactly 100
entries vs. a much larger rolling 48h window) that needs no extra parsing
for a dedicated title element.

## Paywall behavior

`isAccessibleForFree: true` observed on every sampled article. The single
`"premium"` string hit found in one article's raw HTML traces to a
`/news/premium/` SSO-subscription nav link in a `<script>` block, not
article-body gating — no truncated `articleBody`, no "subscribe to
continue reading" marker found on any sampled article. The Tribune's news
content does not appear to be paywalled.

## Known limits

- 404s for deleted/never-existed article slugs are **real HTTP 404s**
  (confirmed on a deliberately-invented slug) — no soft-404 quirk observed.
- `latest` mode is capped at 100 items since `/recent-sitemap.xml` itself
  only ever carries 100 entries — `/sitemap-news.xml`'s larger ~1,200-entry
  window exists as an alternate but isn't wired up, to avoid the extra
  `news:`-namespace parsing path for a marginal recency-window gain.
- Only 3 articles sampled in depth (India/crime, Haryana/crime, World, plus
  one invented-slug 404 probe, plus one Rajasthan/legal article). A
  structurally different template (e.g. opinion/editorial, sports live
  score, photo gallery, or video feature) was not sampled.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If The Tribune redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
