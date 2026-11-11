# Crawling Method — Aftenposten

**Last verified:** 2026-08-24

## WAF

None detected. `aftenposten.no` sits behind no Cloudflare/DataDome/PerimeterX/Akamai/Fastly/Aliyun/Kasada layer that could be found:

- `curl_cffi` `chrome124` returned **200** on the homepage (333 KB), article pages, and `/rss.xml` with no `cf-ray`, `x-datadome-cid`, `x-kasada-tier`, `x-akamai-*` headers and no challenge-body markers.
- `robots.txt` returns 200 and has **no `Disallow` for any AI-bot user-agent** (`Claude`, `ClaudeBot`, `Claude-Web`, `anthropic-ai`, `GPTBot`, `CCBot`, `bytespider`, `Google-Extended` all checked by name — none blocked).

**TLS profile pinned:** `chrome124`, per the portfolio-wide default of avoiding `chrome131` (most-blocklisted profile elsewhere) even though it currently also works here.

## Data sources

### 1. Article pages — `S1-jsonld` (primary)

`GET https://www.aftenposten.no/<section>/i/<id>/<slug>`

The page emits an `application/ld+json` `NewsArticle` block (plus a separate `BreadcrumbList` block) with `headline`, `datePublished`/`dateModified`, `wordCount`, `articleSection`, `description`, `keywords`, `image`, `video`, `publisher`, `author`, `isAccessibleForFree` — but **no `articleBody`**. Full text is pulled separately from the rendered HTML: the `article` container, all `<p>` tags joined with a blank line.

### 2. Latest headlines — `S2-rss`

`GET https://www.aftenposten.no/rss.xml`

Standard RSS 2.0, confirmed live with `title`/`link`/`pubDate`/`description` per `<item>` — no body text.

## Paywall behavior

Aftenposten has a metered subscription paywall in production. Sampled 10 live articles from `/rss.xml` (2026-08-24): 8 had `isAccessibleForFree: true`, 1 had `isAccessibleForFree: false` (wordCount 110 → 826 extracted chars, roughly the same chars-per-word ratio as the free samples — no obvious truncation in this particular sample). This extractor never fabricates text — it records whatever the `article` container actually serves and sets `_paywalled: true` whenever `isAccessibleForFree` is explicitly `false`, same defensive pattern as `aftonbladet-scraper`. Treat `_paywalled: true` + a short `articleBody` as the reliable signal; a `_paywalled: true` record with a long body simply means this particular piece wasn't gated at the content layer.

## Known limits

- **2 of 10 sampled article-shaped URLs (culture/review pages, e.g. `/kultur/artikkel/...`) carry no `NewsArticle` ld+json block at all** — a different, non-news content type, not a site redesign. These raise `NotNewsArticle` internally, caught per-URL in `main.py` and returned as `{"_error": "not_a_news_article"}` rather than crashing the run (same tier as a 404). Stick to standard `/i/<id>/` news-article URLs (from `latest` mode or the site's news sections) for reliable extraction.
- Paywall truncation was only directly confirmed on one short sample (see Paywall behavior above) — the mechanism may be closer to Business Insider/Jakarta Post's cosmetic gate (full text in markup, hidden client-side) than Bild's genuine server-side truncation. Not fully proven either way.
- `latest` mode returns whatever is currently in `/rss.xml` at fetch time; no historical/pagination parameter exists for this feed.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh RSS entry and confirm the `article` selector still returns non-empty `<p>` text. If Aftenposten changes templates, `articleBody` will silently go `null` — that's the trigger to re-inspect the selector, not a crash.
