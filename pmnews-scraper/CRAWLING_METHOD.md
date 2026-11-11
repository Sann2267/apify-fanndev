# Crawling Method — P.M. News Nigeria

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh as the first action of this build. `https://pmnewsnigeria.com/robots.txt` -> HTTP
200, 228 bytes:

```
Disallow: /?s=*
Disallow: /*?s=*
Disallow: /search/

# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:

Sitemap: https://pmnewsnigeria.com/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token
appears anywhere. No blanket `User-agent: * / Disallow: /`. The only per-path disallows are the
site's internal search (`/?s=*`, `/*?s=*`, `/search/`), which this actor never touches. The file
was also read in full for a natural-language AI/scraping/TDM prohibition notice (the check added
after the Star Malaysia incident) — **none found**; it's a plain machine-readable Yoast SEO block
with no legal-notice comment of any kind. Confirmed crawlable.

## WAF

`pmnewsnigeria.com` sits behind **Cloudflare** (`server: cloudflare`, `cf-ray` present) but shows
**no active JA3/TLS-fingerprint challenge** for normal traffic. `curl_cffi` `chrome124` gets a
clean 200 on the homepage, article pages, `/feed/`, `/sitemap_index.xml`, and the WP REST API
(`/wp-json/wp/v2/posts`) — no "Just a moment..." interstitial, no `cf-mitigated` header, no
challenge body on any of the 8 article URLs sampled during recon (News, Politics x2, Metro, Sports
x2, Entertainment x2).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default.

## CMS

WordPress + Yoast SEO plugin. Unauthenticated `wp-json` REST API live at
`/wp-json/wp/v2/posts?slug=<slug>&_embed=1` — confirmed working as a viable fallback data source
(not used as primary since the ld+json + HTML combination is simpler and already sufficient), and
independently confirms the site's real-404 behavior (`?slug=<bad-slug>` returns HTTP 200 with an
empty JSON array `[]`).

**Backend quirk:** several ld+json `@id` values (the article's `isPartOf`/`WebSite` node, the
author node) point at a raw origin-server IP (`http://34.243.69.150/#website`,
`http://34.243.69.150/#/schema/person/...`) instead of the public domain — a `siteurl`
misconfiguration on the WordPress backend. Harmless for this actor since only `.name`/`.headline`/
etc. fields are ever read off these nodes, never the `@id` URLs themselves.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://pmnewsnigeria.com/<year>/<month>/<day>/<slug>/`

The page emits **one** `<script type="application/ld+json" class="yoast-schema-graph">` block — a
Yoast-SEO-style `@graph` array of 6 cross-referenced nodes: `Article`, `WebPage`, `ImageObject`,
`BreadcrumbList`, `WebSite`, `Person`.

**The article node's `@type` is `"Article"`, not `"NewsArticle"`** — confirmed on all 8 sampled
articles across News, Politics, Metro, Sports, and Entertainment sections. The extractor's node
matcher checks both `{"NewsArticle", "Article"}` for portfolio-wide consistency/robustness, but
only `"Article"` was ever actually observed here.

The `Article` node carries `headline`, `datePublished`, `wordCount`, `keywords`, `articleSection`
(e.g. `["US"]`), `thumbnailUrl`, and an **inline** `author` object (`{"name": "Ayorinde Oluokun",
"@id": "http://34.243.69.150/#/schema/person/..."}` — name already present, same pattern as
`punch-scraper`, no `Person`-node round-trip strictly required) — but **no `articleBody`**, same
gap as every other WordPress+Yoast outlet in this portfolio.

**There is no `Organization`/`publisher` node in the graph, AND no `og:site_name` meta tag on this
site either** (both confirmed absent on every sampled article — unlike `punch-scraper`, which has
the meta tag even without an Organization node). `publisher` is instead read from the graph's own
**`WebSite` node's `name` field** (`"P.M. News"`), which is present and reliable on every sample.

**Quirk — `author.name` is the publishing account, not necessarily the reporter:** the ld+json
`author.name` (e.g. `"Ayorinde Oluokun"`, `"Michael Adesina"`) is the WordPress user account that
published the post — often a desk editor — not necessarily the journalist who wrote it. The real
reporter's name frequently appears as the article body's own first line (`"By Tiamiyu Prudence
Arobani"`, `"By Kazeem Ugbodaga"`, `"By Constance Athekame"`, `"By Zubairu Idris"` — 4 different
names observed across the 6 in-depth samples, all distinct from the `author.name` on those same
pages). This line is left untouched inside `articleBody` (raw passthrough — it's genuine article
content) rather than parsed out as a separate field, since the pattern ("By " at the start of the
first paragraph) is a content convention, not a structured data field, and isn't 100% guaranteed
to be present on every article template.

Full body text comes from HTML: **`div.article_body`**, direct-child `<p>` tags only
(`recursive=False`). Confirmed present with this exact class and consistent direct-child structure
across all 6 samples checked in depth (23, 9, 16, 21, 33, and 10 paragraphs respectively).

**Bonus field unique to this site (not seen elsewhere in this portfolio):
`div.quick_summary_box`** — an `<h4><img .../> Quick Read</h4>` label followed by exactly one
`<p>` of desk-written summary text, structurally identical to the RSS feed's own `<description>`
content. Captured as `quickSummary` (the `<p>` text only; the "Quick Read" label is excluded).
Confirmed present on all 6 in-depth samples.

`description` is pulled from `<meta name="description">`, falling back to the ld+json `WebPage`
node's own `description` field if the meta tag is ever missing (not observed missing on any
sample).

A page that 200-OKs but is not an article (e.g. `/privacy-policy/`, `/contact-us/`) emits a
`WebPage`/`BreadcrumbList`/`WebSite` graph with **no `Article` node** — detected explicitly and
reported as `_error: "not_article"` (both static pages confirmed during recon).

A genuinely deleted/never-existed slug returns a **REAL HTTP 404** (confirmed on a
deliberately-invented slug both directly and via the WP REST API, which returns HTTP 200 with an
empty `[]` for the same slug) — no soft-404 quirk on this site, unlike `premiumtimesng.com`.

### 2. Latest headlines — `S2-rss`

`GET https://pmnewsnigeria.com/feed/`

A stock WordPress feed (unlike Punch's custom `rss.punchng.com` aggregator or This Day's broken
feed). 30 items returned in a single request during recon, no pagination needed for this actor's
50-item cap.

Fields observed: `title`, `link`, `pubDate`, **`dc:creator` — a REAL per-article byline that
varies article-to-article** (`"Ayorinde Oluokun"`, `"Michael Adesina"` both observed across 5
sampled items — unlike Punch's feed, which always emits the same generic value), one or more
**REAL `<category>` tags** (section + tag values, e.g. `["US", "United States", "Visa
Revocation"]` — unlike Punch's always-empty category), a `guid` in the `?p=<numeric-id>`
query-string format (**not** the same as `link`, unlike Punch's feed where guid==link), and a
teaser `description` (plain text, content-identical in style to the article page's own
`quickSummary` box).

**No `<enclosure>` tag on this feed** (confirmed absent on every sampled item, unlike Punch's feed
which has one on every item) — no `enclosureUrl` field is emitted by this actor's `S2-rss` records.

The Yoast `sitemap_index.xml` was also confirmed present and would be a viable fallback `latest`
source, but `/feed/` was chosen as primary since it needs no sub-sitemap discovery round-trip and
returns real per-article bylines/categories that the RSS-only actors elsewhere in this portfolio
often lack.

## Paywall behavior

**None found.** The string "subscribe" appears in sampled article HTML, but only inside a
newsletter-signup widget's JavaScript (`POST /wp-json/pmnews/v1/subscribe`) — not a content gate.
No "paywall"/"premium"/"member-only"/"metered" marker was found blocking or truncating article
text on any of the 8 sampled articles. P.M. News is a free, open-access site.

## Known limits

- 404s for deleted/never-existed article slugs are **real HTTP 404s** (confirmed on a
  deliberately-invented slug, cross-checked against the WP REST API) — no special soft-404
  detection was needed.
- A 200-OK page that isn't an article (e.g. `/privacy-policy/`, `/contact-us/`) emits a
  `WebPage`/`BreadcrumbList`/`WebSite` ld+json graph with no `Article` node — detected explicitly
  and reported as `_error: "not_article"`.
- `author` (from ld+json) is the WordPress publishing account, which can differ from the real
  reporter named inside `articleBody`'s own first line — see the quirk above. Not parsed out as a
  separate field since the "By <name>" convention isn't guaranteed on every template.
- `/feed/` has no `<enclosure>` tag, so `latest`-mode records carry no thumbnail field at all — use
  `article` mode's `thumbnailUrl` for a lead image.
- Only 8 articles sampled in depth (News x2, Politics x2, Metro, Sports x2, Entertainment x2, plus
  two non-article pages and one invented-slug 404 probe). A live-blog, video-feature, or
  photo-gallery template, if this site has one, was not sampled.

## Diff cadence

Quarterly smoke test recommended.
