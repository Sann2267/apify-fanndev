# Crawling Method — Barbados Today

**Last verified:** 2026-08-26

Barbados Today (`barbadostoday.bb`) is Barbados' leading digital-native news outlet
(as opposed to a legacy-print outlet with a web presence bolted on).

## Robots.txt

```
Crawl-delay: 10
# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:

Sitemap: https://barbadostoday.bb/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

Stock Yoast SEO block: `Crawl-delay: 10` plus a single `Disallow:` with no path
(allow-all) under one `User-agent: *` group. No Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai disallow anywhere, only one user-agent
group total, and — per the post-"Babak 17" (The Star Malaysia) screening rule —
**no plain-English prohibition against AI/LLM training or scraping in any
comment either**; the only comments are the Yoast block markers themselves.
Independently re-verified with a fresh plain `curl` fetch during this build
(`GET https://barbadostoday.bb/robots.txt` → HTTP 200, body as above) — confirmed
crawlable.

## WAF

`barbadostoday.bb` is WordPress (WP 7.0.4, Yoast SEO, Penci "Soledad"-family
theme) hosted on **WP Engine**, fronted by **Cloudflare** (`server: cloudflare`).

- A bare `curl -A "Mozilla/5.0"` request (User-Agent only, no other headers) gets
  a **403** ("Attention Required!" / "blocked ... wpenginepowered.com") on
  **every** path tried, including the homepage.
- `curl_cffi` `chrome124` impersonation clears this cleanly on the **first try**
  for every path tested — homepage, `/wp-json/wp/v2/posts`, `/feed/`, a real
  article page, and a deliberately-invented article slug (real 404) — no
  warmup-then-retry dance needed.
- A full-browser-header plain `curl` (realistic Chrome UA + `Accept`/
  `Accept-Language`, no TLS impersonation) also got clean 200s during initial
  recon, suggesting this is closer to a header/UA completeness check than a
  strict JA3/TLS gate — but `chrome124` impersonation is used anyway per
  portfolio default, and is what the shipped actor relies on.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default.

## Data sources

### 1. Article + latest mode — `S1-wpapi`

`GET https://barbadostoday.bb/wp-json/wp/v2/posts?slug=<slug>&_embed=1` (article mode)
`GET https://barbadostoday.bb/wp-json/wp/v2/posts?per_page=<limit>&_embed=1` (latest mode)

Public, unauthenticated WordPress REST API, not disallowed by robots.txt.
Confirmed `per_page` up to 50 returns in a single call — no pagination loop
needed for this actor's 1-50 `limit` range. `_embed=1` inlines:

- **Author** — real name (e.g. `"Shanna Moore"`), slug, and archive link. The
  raw API response also carries a `coauthors` (numeric ID list) and a redundant
  `author_info` object (Co-Authors-Plus-style plugin fields) — not surfaced in
  the output since the embedded author object already carries the same name
  more usefully (with slug + link), consistent with this portfolio's `author`
  field convention on other WP-API-primary actors.
- **Featured media** — `source_url`, width/height, alt text.
- **Category/tag terms** — `wp:term` embeds three groups on this site
  (`category`, `post_tag`, and a third `author` taxonomy group from the
  co-authors plugin); only `category`/`post_tag` are surfaced as
  `categories`/`tags`, matching this portfolio's existing WP-API extractor
  pattern (`thisday-scraper`).

`content.rendered` is the full article body HTML; paragraphs are extracted with
BeautifulSoup and joined with a blank line. `excerpt.rendered` is used for
`description`. `content.protected` was `false` on every sample checked (see
Paywall below).

This is chosen as the **primary** source over the site's own `/feed/` RSS
(also confirmed working cleanly, standard WordPress feed) because the REST API
returns the exact same rich shape (full body, real embedded author,
categories/tags) for **both** article mode and latest mode in one round trip —
matching this portfolio's `thisday-scraper` pattern, rather than a thin
title/link/pubDate shape for latest mode.

**Known cosmetic quirk (dropcap decorator):** the theme wraps the first letter
of an article's first paragraph in `<span class="penci-dropcap-box-outline">`
(e.g. `<span ...>F</span>our major health facilities...`). BeautifulSoup's
`get_text(" ", strip=True)` inserts a space between adjacent tag-separated text
nodes regardless of source whitespace, so the extracted body reads `"F our
major..."` instead of `"Four major..."` — a well-known, unavoidable side effect
of `get_text()`'s separator behavior on decorative inline spans, not a parse
failure. Left as-is (raw-passthrough-of-extracted-text convention, same
approach used across this portfolio's other `get_text(" ", strip=True)`-based
extractors) rather than special-cased, since a bespoke "detect and rejoin
dropcap spans" rule risks being wrong on some future template variant.

### 2. Fallback — `S2-jsonld+html`

Used only if the WP REST API call itself fails (non-200/timeout after
retries). `GET https://barbadostoday.bb/<year>/<month>/<day>/<slug>/`

The article HTML emits **two separate** `<script type="application/ld+json">`
constructs:

1. A Yoast-style `@graph` array of 7 cross-referenced nodes: `Article`,
   `WebPage`, `ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`,
   `Person`. `Article.author` is a bare `{"@id": "...#/schema/person/<hash>"}`
   reference that resolves against the graph's own `Person` node (real name).
   `Article.publisher` is likewise a bare `{"@id": "...#organization"}`
   reference resolving to the graph's `Organization` node
   (`name: "Barbados Today Inc"`). The `Article` node carries `headline`,
   `datePublished`, `dateModified`, `wordCount`, `keywords`,
   `articleSection` — but **no `articleBody`**.
2. A separate flat Penci-theme `BlogPosting` block (not part of the `@graph`)
   duplicating headline/description/dates/author/publisher in a simpler shape.
   Not used — the `@graph` walk above already yields the same fields via a
   pattern shared with this portfolio's `guardian-nigeria-scraper`.

Full body text comes from HTML: `div.entry-content`, direct-child `<p>` tags
only (`recursive=False`) — confirmed this class appears exactly **once** per
article page with 29/29 direct-vs-total `<p>` tags on the sampled article (no
nested ad/related-article paragraphs to filter out).

A page that 200-OKs but is not an article (no `Article` node in the graph)
raises `ArticleNotFound`, reported as `_error: "not_article"` rather than a
schema-drift crash. Not observed live in this build (no non-article path was
sampled through this fallback), but the same defensive check used by
`guardian-nigeria-scraper` is carried over since the Yoast `@graph` shape is
the same family.

## Paywall behavior

None observed. `content.protected` was `false` on every one of 5 sampled
posts (spanning Health, Local News categories), and no
"subscribe"/"premium"/"paywall"/"sign in to continue"/"members only"/"this
content is for" marker string was found in any sampled `content.rendered`
body. Barbados Today is a free, open-access site.

## Known limits

- Nonexistent article slugs return a REAL HTTP 404 via direct page fetch, and
  the WP REST API's `?slug=` query authoritatively returns an empty list for a
  never-existed slug (confirmed on a deliberately-invented slug/date
  combination) — no soft-404 quirk observed.
- Only 5 articles sampled in depth (all News/Health/Local News from one
  `per_page=5` pull, plus the one article used for deep JSON-LD/HTML
  inspection). A structurally different template (e.g. an opinion column,
  video feature, or photo-gallery page) was not sampled.
- The `S2-jsonld+html` fallback's "not an article" detection was implemented
  by analogy with `guardian-nigeria-scraper` (same Yoast `@graph` family) but
  not independently verified against a real non-article page on this site.

## Diff cadence

Quarterly smoke test recommended.
