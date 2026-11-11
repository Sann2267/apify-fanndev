# Crawling Method — La Nación

**Last verified:** 2026-08-25

## WAF

`www.lanacion.com.ar` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on the homepage, article pages, RSS feed, and all
sitemaps -- no challenge body, no 403.

`robots.txt` only disallows internal utility/form paths (`/pf/api/`,
`/buscador`, `/Suscripcion`, `/registracion`, `/herramientas`,
`/weblogs/*`, `/wsj/*`, etc.) -- no Claude/GPTBot/anthropic-ai disallow of
any kind. It also advertises 6 `Sitemap:` entries, including
`sitemap-news.xml` and a `sitemap-section-index.xml`.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

Site runs on **Arc Publishing** (same CMS family as `eluniversal-scraper`)
-- confirmed by `/pf/` static-resource paths in robots.txt and the
`/arc/outboundfeeds/...` feed/sitemap namespace.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.lanacion.com.ar/<section>/<slug>-nid<date>/`

Each article page emits 5-10 separate `application/ld+json` blocks
(`NewsMediaOrganization`, `WebSite`, `BreadcrumbList`, plus the article
node itself). Regular news stories use `@type: "NewsArticle"`; opinion
columns use a distinct `@type: "OpinionNewsArticle"` (same shape, plus a
`creator` array and an individual `Person` byline instead of the
`Organization` byline used for staff/wire stories) -- the extractor
accepts either type via `KNOWN_ARTICLE_TYPES` and raises `UnexpectedShape`
for anything else (e.g. a live-blog or video-only page type, not sampled).

**`articleBody` is present in full directly in the ld+json** -- confirmed
on 25 articles spanning `politica`, `el-mundo`, `sociedad`, `seguridad`,
and `opinion` sections, from short breaking-news briefs (~1.6K chars) to
long-form opinion columns (~8.2K chars). No HTML fallback selector is
needed, unlike `tass-scraper`/`eluniversal-scraper`.

Field notes:
- `author` — a dict (`{"@type": "Organization", "name": "LA NACION"}`) for
  staff/wire content, or a list of `{"@type": "Person", "name": ...}`
  dicts for bylined opinion columns. Normalized to a comma-joined name
  string (`_normalize_author`).
- `publisher` — only a JSON-LD `@id` reference
  (`{"@id": "https://www.lanacion.com.ar/#organization"}`), never a
  resolved name. Passed through raw rather than fabricated.
- `image` and `keywords` — already list-shaped in the source JSON (unlike
  `eluniversal-scraper`'s comma-separated `keywords` string) -- passed
  through verbatim, no reshaping needed.

### 2. Latest headlines — `S2-rss`

`GET https://www.lanacion.com.ar/arc/outboundfeeds/rss/`

Standard RSS 2.0 (`title`/`link`/`guid`/`pubDate`/`description`/
`category`) plus a `content:encoded` CDATA block carrying the **full**
article HTML per item. This actor does **not** parse `content:encoded` in
`latest` mode, to keep headline listings lightweight and consistent with
the rest of the portfolio -- use `article` mode against `link` for the
full clean-text record (with the richer ld+json metadata: author,
keywords, dates, paywall flag, etc).

Confirmed live and chronological: `lastBuildDate` matched request time,
and top items matched the freshest URLs in `sitemap-news.xml`.

## Paywall behavior

**Genuine metered/subscription infrastructure exists, but no truncation
was observed in the server-rendered ld+json.** Every sampled article
carries `isAccessibleForFree` (bool), and many also carry an `isPartOf`
block naming the subscription product, e.g.:

```json
"isPartOf": {
  "@type": ["CreativeWork", "Product"],
  "name": "Acceso Digital Monthly Test",
  "productID": "lanacion.com.ar:acceso_digital"
}
```

This is clear evidence La Nación runs a metered paywall for human readers.
However, **all 25 sampled articles** during recon -- across breaking
political news, a live-developing crime case, science/health explainers,
and 6 opinion columns from named columnists (typically the most
paywall-guarded content tier at most outlets) -- came back with
`isAccessibleForFree: true` and a full, non-truncated `articleBody` (body
text ends on a complete sentence in every sample, no CTA/ellipsis
truncation marker). 15 sequential fetches in a single cookie-persisting
session also showed no metering kick-in (no cookies were even set by the
server). The most likely explanation: the paywall is enforced **client-side
via JS** for the human reading experience, while the server-rendered
HTML/ld+json (read by this actor, and presumably by search crawlers) is
always served in full.

Because this behavior could differ for content this actor didn't sample
(e.g. print-edition-exclusive pieces, live blogs, or a future tightening
of the metering), the raw `isAccessibleForFree` and `isPartOf` fields are
passed through on every record, and a derived `_paywalled` boolean is set
to `True` only when `isAccessibleForFree` is explicitly `false` --
defensive by construction, never fabricated.

## Known limits

- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  slug) -- no soft-404 behavior observed.
- `sitemap-section-index.xml` only lists a handful of niche categories
  (`opinion`, `salud`, `tecnologia`, `loterias`, `propiedades`, magazine
  supplements) -- the bulk of daily news (politica, economia, el-mundo,
  deportes) is covered by `sitemap-news.xml` / the RSS feed instead, not
  by a per-section sitemap.
- Only `NewsArticle` and `OpinionNewsArticle` ld+json types were sampled.
  A structurally different page type (live-blog, video-only, photo
  gallery) was not encountered and would raise `UnexpectedShape` rather
  than silently emit a wrong or empty record.
- `latest` mode's `description` is a short teaser (RSS standard) -- use
  `article` mode against `link` for the full body.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and an opinion-column URL, and confirm `isAccessibleForFree`
is still observed as `true` for ordinary content -- if La Nación starts
truncating `articleBody` for non-free articles, `_paywalled` will flip to
`true` automatically and no code change is needed, but it's worth
re-verifying the ratio.
