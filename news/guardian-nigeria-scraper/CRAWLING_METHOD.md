# Crawling Method — Guardian Nigeria

**Last verified:** 2026-08-26

The Guardian Nigeria (`guardian.ng`) is a major Nigerian daily newspaper. It is
**not related to the UK's The Guardian** (`theguardian.com`, already covered
by this portfolio's `guardian-scraper`) — separate publisher, separate
domain, separate owner.

## Robots.txt

```
#Sitemap: https://guardian.ng/wp-sitemap.xml
Sitemap: https://guardian.ng/news-sitemap.xml
Sitemap: https://guardian.ng/sitemap_index.xml
#Sitemap: https://guardian.ng/sitemap.xml

# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:
# ---------------------------
# END YOAST BLOCK
```

Stock Yoast SEO block: a single `Disallow:` with no path (allow-all) under
one `User-agent: *` group. No Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai disallow anywhere, and only one user-agent
group total. Independently re-verified with a fresh `curl_cffi` `chrome124`
fetch during this build (`GET https://guardian.ng/robots.txt` -> HTTP 200,
body as above) — confirmed crawlable.

**Note:** a plain UA-only `curl`/`requests` baseline (no TLS impersonation)
gets a Cloudflare **managed JS challenge** page ("Just a moment...") instead
of the real robots.txt body — `curl_cffi chrome124` impersonation is required
even for this first request, not just for article pages. See WAF section.

## WAF

`guardian.ng` sits behind **Cloudflare** (`server: cloudflare`). Two very
different behaviors were found depending on the path:

- **Homepage, article pages, `/news-sitemap.xml`, `/wp-sitemap.xml`,
  `/wp-json/wp/v2/posts`** — clean HTTP 200 with `curl_cffi` `chrome124` on
  the first try, no warmup-then-retry dance needed. A plain
  `requests`/`curl` baseline (no impersonation) instead gets the Cloudflare
  managed-challenge interstitial on every one of these paths.
- **`/feed`, `/feed/`, `/latest-news/`** — a hard Cloudflare 403 ("Attention
  Required!") on **every** TLS profile tried (`chrome124`, `chrome131`,
  `chrome99_android`, `safari17_0`, `edge101`, `firefox133`) — a
  path-specific WAF rule (likely a rate-limit/known-scraping-target block on
  the classic WordPress feed endpoint and the "latest news" listing page),
  not a general fingerprint gap, since the exact same profile 200s cleanly
  on the homepage and article pages moments before/after.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. `latest` mode is built on `/news-sitemap.xml` instead of `/feed` to
route around the path-specific block entirely (see Data sources below).

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://guardian.ng/<section>/<slug>/`

The page emits **one** `<script type="application/ld+json">` block — a
Yoast-SEO-style `@graph` array of 7 cross-referenced nodes: `NewsArticle`,
`WebPage`, `ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`,
`Person`.

The `NewsArticle` node carries `headline`, `datePublished`, `dateModified`,
`wordCount`, `keywords`, `articleSection` (e.g. `["Featured", "News"]`),
`thumbnailUrl` — but **no `articleBody`**.

**Unlike Punch (no `Organization` node at all in the graph) and Premium
Times (`author` as a bare `{"@id": ...}` reference), this site's
`NewsArticle.author` is a LIST of fully inline `Person` objects** — each
carrying `name`, a full bio paragraph in `description`, `url` (author
archive page), `image`, and `sameAs` (social links). Only `name` is
surfaced in the output (comma-joined across multiple authors); the bio/
image/social fields are dropped as out of scope for this actor's schema.

**`publisher` IS a bare `{"@id": "https://guardian.ng/#organization"}`
reference on this site** — unlike Punch, which has no `Organization` node
at all and falls back to `<meta property="og:site_name">`. Here the
reference resolves cleanly against the graph's own `Organization` node
(`name: "Guardian Nigeria"`), so that's used directly; the
`og:site_name` fallback (`"The Guardian Nigeria News - Nigeria and World
News"`) is only used if the `Organization` node is ever missing.

**No double-HTML-escaping quirk observed** in this graph's text values on
any of the 4 samples checked (headline, keywords, articleSection all come
through clean, no literal `&amp;` etc.) — unlike Punch's
`"Business &amp; Economy"`. `html.unescape()` is still applied to every
text value pulled from the graph for robustness against a future shape
change; it's a no-op when there's nothing to unescape.

Full body text comes from HTML: `div.post-content`, **direct-child `<p>`
tags only** (`recursive=False`). Confirmed the literal `class="post-content"`
string appears **exactly once** per article page (checked via a direct
string search across the full page HTML, which also contains a large
inline `<style>` block referencing `.post-content` many times as CSS
selectors — those don't collide with the actual DOM element count). Ad
slots (`<div class="ad-container">`) sit as direct children alongside the
`<p>` tags inside the same container — they're skipped automatically by
the `find_all("p", recursive=False)` tag-name filter, no extra scoping
needed.

`description` is pulled from `<meta name="description">`, falling back to
the ld+json `WebPage` node's own `description` field if the meta tag is
ever missing (not observed missing on any of the 4 samples).

### 2. Latest headlines — `S2-sitemap`

`GET https://guardian.ng/news-sitemap.xml`

A Yoast News SEO sitemap (referenced from `robots.txt`), used instead of
`/feed` because `/feed` is hard-blocked (see WAF above). 295 `<url>` entries
observed in one fetch. Each carries `loc`, and a `news:news` block with
`news:publication` (`news:name`, `news:language`), `news:publication_date`
(real per-article ISO 8601 timestamp), and `news:title`. Confirmed
already newest-first in file order (top entry matched the freshest
homepage headline at fetch time) — `extract_sitemap_items()` still sorts
descending by `news:publication_date` defensively, in case that ordering
isn't guaranteed on every fetch.

The `wp-json/wp/v2/posts` REST API was also confirmed to return a clean 200
and would be a viable alternative, but the news sitemap was chosen since it
already carries a real title and per-article timestamp in one lightweight
XML request with no extra pagination/param discovery needed.

## Paywall behavior

None observed. "subscribe"/"premium" string hits (a small, constant count
across every sampled page) trace to a newsletter-signup widget and site nav,
not article-body gating — no truncated `articleBody`, no
"subscribe to continue reading" marker found on any of the 4 sampled
articles (News x2, Business, plus one non-article and one invented-slug
probe). Guardian Nigeria is a free, open-access site.

## Known limits

- 404s for deleted/never-existed article slugs are **real HTTP 404s**
  (confirmed on a deliberately-invented slug) — no soft-404 quirk observed.
- A 200-OK page that isn't an article at all (e.g. `/privacy-policy/`)
  emits a `WebPage`/`BreadcrumbList`/`WebSite`/`Organization` ld+json graph
  with no `NewsArticle` node — detected explicitly and reported as
  `_error: "not_article"`.
- `/feed`, `/feed/`, and `/latest-news/` are hard-blocked (403) regardless
  of TLS profile — `latest` mode routes around this via
  `/news-sitemap.xml` instead, which was never observed blocked.
- Only 4 articles sampled in depth (News x2, Business, plus one non-article
  page and one invented-slug 404 probe). A structurally different template
  (e.g. a live-blog, video feature, opinion/cartoon, or photo-gallery page)
  was not sampled.

## Diff cadence

Quarterly smoke test recommended.
