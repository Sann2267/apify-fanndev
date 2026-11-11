# Crawling Method — Hindustan Times

**Last verified:** 2026-08-24

## WAF

None detected. `hindustantimes.com` returns 200 on homepage, article pages,
and the India-news RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.hindustantimes.com/<section>/<slug>-<id>.html`

Each article page emits a single `application/ld+json` `NewsArticle` block
(bare dict). It carries `articleBody` with the **full plain-text article**
(1,200-3,900 characters across 5 samples), `headline`, `description`,
`keywords` (comma-separated string, not an array — unlike most other outlets
in this portfolio), `articleSection`, `author` (array, often an
`Organization` like "HT News Desk" rather than a named `Person`),
`associatedMedia`/`image`, and `datePublished`/`dateModified`.

**Quirk:** `headline` and `description` both carry a `" | <Section Name>"`
suffix (e.g. `"...in Delhi | India News"`) baked in by the CMS as an SEO
title-tail. This is passed through verbatim per raw-passthrough convention —
downstream consumers wanting a clean headline should strip everything from
the last `" | "` onward themselves.

No `isAccessibleForFree`/`hasPart` paywall-signal fields were observed on any
sampled article (unlike LA Times/Vox in this portfolio) — Hindustan Times'
main news content does not appear to carry a schema.org paywall marker.

No `__NEXT_DATA__` was found — this site does not expose page state via
Next.js SSR data injection.

### 2. Latest headlines — `S2-rss`

`GET https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml`

Standard RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`, `guid`,
`pubDate`, `description`. No single site-wide feed was found during recon
(unlike Economic Times/LA Times); this section-specific feed
(`india-news`) is used as the default since it was the one confirmed live
and chronological (5 samples, 2026-08-24, all within hours). Other section
feeds (e.g. `world-news`) exist at the same `/feeds/rss/<section>/
rssfeed.xml` pattern and were also spot-checked live, but are not wired up
as alternates to avoid an undocumented section-ID list that could rot.

## Paywall behavior

No paywall markers or truncation observed on any sampled article.

## Known limits

- `latest` mode only covers the `india-news` section by default —
  `world-news`/other section feeds exist but aren't exposed as an input
  option; add one if broader latest-mode coverage becomes a requirement.
- `keywords` is a comma-separated string in the JSON-LD, not an array like
  most other outlets in this portfolio — passed through as-is, not split.
- `headline`/`description` carry an SEO title-tail suffix (see Quirk above).

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Hindustan Times redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
