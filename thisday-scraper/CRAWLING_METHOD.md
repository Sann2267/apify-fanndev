# Crawling Method — This Day Nigeria

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh as the first action of this build. `https://www.thisdaylive.com/robots.txt` → HTTP
200, 1113 bytes:

```
# Allow all bots access to the site except for specific crawlers
User-agent: *
Disallow: /wp-admin/
Disallow: /wp-includes/
Disallow: /wp-content/plugins/
Disallow: /wp-content/themes/
Disallow: /private/
Disallow: /secret-page/
Disallow: /page/
Disallow: */page/

Allow: /wp-content/uploads/
Allow: /wp-content/themes/thisdaylive/

User-agent: Bytespider
Disallow: /

User-agent: SemrushBot
Disallow: /

User-agent: PetalBot
Disallow: /

User-agent: Amazonbot
Disallow: /

User-agent: Bingbot
Disallow: /

Sitemap: https://www.thisdaylive.com/sitemap.xml

Disallow: /*?amp=1

User-agent: *
Disallow: /wp-admin/
Disallow: /wp-login.php
Disallow: /wp-register.php

# Added 2026-08-10: junk crawlers observed at high volume in access logs
User-agent: DotBot
Disallow: /

User-agent: Baiduspider
Disallow: /
```

No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token
appears anywhere in the file. There are two `User-agent: *` blocks (both disallow only
admin/system paths, not the whole site) plus several single-purpose full-site blocks for named
crawlers this site's operator wants to keep out (Bytespider, SemrushBot, PetalBot, Amazonbot,
Bingbot, DotBot, Baiduspider) — none of those apply to this actor's user agent. `/wp-json/` (the
REST API this actor relies on) is not disallowed anywhere.

## WAF

**No WAF, no challenge, no bot-manager cookie of any kind.** `curl_cffi` `chrome124` gets a clean
200 on the homepage, article pages, and the WP REST API. Even **plain `curl` with no TLS
impersonation at all** gets a clean 200 on the homepage and the REST API, and a real `HTTP 404` on
a deliberately-invented article slug — confirming there is no TLS/JA3-specific gate either. The
site is served through CloudFront in front of an Apache/Amazon-Linux origin with W3 Total Cache
(page/object/DB caching via Memcache) — a caching layer, not an anti-bot layer.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default (not strictly
required here — plain `curl` works too — but kept for consistency and defense-in-depth).

## CMS

WordPress (`<generator>https://wordpress.org/?v=6.8.8</generator>` in the RSS feed; `Site Kit by
Google 1.156.0` generator meta on article pages), unauthenticated `wp-json` REST API live at
`/wp-json/wp/v2/posts`.

## Data sources

### 1. Article pages AND latest headlines — `S1-wpapi` (primary, used for both modes)

`GET https://www.thisdaylive.com/wp-json/wp/v2/posts?slug=<slug>&_embed=1` (article mode)
`GET https://www.thisdaylive.com/wp-json/wp/v2/posts?per_page=<limit>&_embed=1` (latest mode)

This is the **only** rich structured data source on this site — confirmed during recon that
article pages carry **zero JSON-LD** (`<script type="application/ld+json">`) anywhere (checked
across 4 sampled pages spanning News/Sport/Education/Metro) and almost no OpenGraph metadata
either (only `og:image` is present on every sampled page; `og:title`, `og:description`,
`article:published_time`, `article:modified_time`, and `name="author"` are all absent). The WP
REST API is therefore not just the *preferred* source (as on other WordPress actors in this
portfolio) but the *only* source of headline/body/author/date/category data this site's HTML
doesn't otherwise expose at all.

`_embed=1` inlines:
- **`content.rendered`** — the full article body as WordPress HTML.
- **`_embedded.author[0].name`** — the real per-article byline (e.g. `"Emmanuel Addeh"`,
  `"Uchechukwu Nnaike"`).
- `_embedded.wp:featuredmedia[0]` — lead image with `source_url`/`media_details.width`/`height`.
- `_embedded.wp:term` — `category` and `post_tag` term objects.

A slug with no matching post returns `HTTP 200` with an **empty JSON array `[]`** — not a 404 — so
`_try_wpapi` treats an empty list as authoritative `not_found` (verified against a synthetic
`this-slug-does-not-exist-zzz999-abc` slug). The real HTML page for the same invented slug returns
a genuine `HTTP 404` (verified with plain `curl`), consistent with the API's answer.

**Latest mode reuses the exact same endpoint and parser**, just without the `slug` filter
(`?per_page=<limit>&_embed=1`). `per_page=50` was confirmed to return 50 full posts in a single
call (530 KB response, no truncation, no pagination needed) — well above this actor's 50-item
`limit` cap. This means **latest-mode records here carry the same rich shape as article-mode
records** (full `articleBody`, real author, categories/tags) rather than a thin RSS-style
title/link/pubDate shape used elsewhere in this portfolio — a direct benefit of this site's RSS
feed being broken (see below).

**Key quirk — empty-title/numeric-slug posts:** 1 of 20 posts sampled from `/wp-json/wp/v2/posts?
per_page=20` had an **empty `title.rendered`** (`""`) and a **purely numeric `slug`** equal to the
post's own ID (e.g. `"slug": "1240482"`, `"link":
".../2026/08/26/1240482/"`) — despite carrying a full, real, multi-paragraph `content.rendered`
body. This looks like a publish-workflow glitch on the CMS side (a draft force-published without a
title/slug ever being set), not a parse failure — confirmed by fetching that exact post directly
(`/wp-json/wp/v2/posts/1240482`) and seeing real article content about a Nigerian Navy maritime
security programme. `headline` is legitimately `None`/empty for these records; the extractor does
**not** raise `UnexpectedShape` for an empty title, only for a missing `content.rendered` key
entirely.

### 2. Article pages — `S2-html` (fallback, used only if S1 fails)

If the WP REST API call itself errors out after retries (non-200, timeout, malformed JSON), the
actor falls back to fetching the article's HTML page directly. Because there is no ld+json and
almost no OpenGraph metadata on this site (see above), this fallback is materially **degraded**
compared to every other WordPress actor in this portfolio's S2 path:
- Body text: `section#single_article div.article-content`, all `<p>` tags — confirmed present and
  consistent across 3 sampled article pages (News/Sport/Education, 13-19 paragraphs each).
- Headline: `<title>` tag with the `" – THISDAYLIVE"` site-name suffix stripped via regex, falling
  back to `section#single_article h1` if the title tag is empty.
- `description`, `date`, `author`: always `None` on this path — no reliable source for any of them
  was found anywhere in the raw article HTML. (The page does render human-readable relative
  timestamps like "5 hours ago" in a `.date`-classed element, but these are relative, not absolute,
  and not a reliable machine-parseable date — not used.)

Verified working end-to-end by calling `extract_article_html_fallback` directly against a real
article's HTML — correctly recovered headline + full body text (see captured output below) — but
was never triggered in the normal `process_article` flow during testing since the REST API was
reachable on every sampled article; it exists purely as the defense-in-depth fallback the
portfolio convention calls for.

### 3. Latest headlines — RSS feed (`/feed/`) — **NOT USED, confirmed broken**

`GET https://www.thisdaylive.com/feed/` was checked as the conventional WordPress latest-mode
source and found to be **unreliable**: the very first fetch during recon returned the correct
~141 KB feed of real current headlines, but every fetch after that (6 consecutive requests, 1s
apart) instead returned a completely different, tiny (1157-byte) feed — literally titled
`"Comments on: 18"` — the WordPress *comments* feed for post/attachment ID 18/577662, dated
**November 2021**, nearly 5 years stale. This is not a proxy/client-side artifact: the response
carries the site's own W3 Total Cache HTML comment footer
(`<!-- Performance optimized by W3 Total Cache... Page Caching using Disk: Enhanced (Requested URI
contains query)... Served from: www.thisdaylive.com @ 2026-08-26 03:51:46 by W3 Total Cache -->`),
confirming the site's own edge/page cache is serving the wrong cached object for the `/feed/` URL
— a server-side misconfiguration, not an actor-side bug. `?paged=2` and `?paged=100` on `/feed/`
both also returned byte-identical content to `?paged=1` in a separate check, showing the feed
doesn't even paginate reliably either. Given this, `/feed/` is not used anywhere in this actor —
latest mode relies entirely on the WP REST API (`S1-wpapi`, see above), which was reliable and
fresh on every request during testing.

## Paywall behavior

**None found.** `content.protected` (WordPress's own field for password-protected content) was
`false` on every sampled article. No "subscribe"/"paywall"/"member-only"/"metered" marker gates
article content anywhere — the one hit for the string "premium" in a sampled article was an
unrelated mention of a mortgage-loan "Premium" contribution tier, not a paywall. Every article
sampled, including same-day-published ones, returned full unrestricted `articleBody` text via the
REST API.

## Known limits

- The WP REST API is the *only* rich data source on this site (no ld+json, almost no OpenGraph) —
  `S2-html` exists for defense-in-depth but is meaningfully degraded (headline + body only, no
  author/date/description) if the API ever becomes unavailable.
- `headline`/`slug` can legitimately be empty/numeric for a small number of posts (a real CMS
  glitch, not a bug here) — see the empty-title quirk above.
- This site's `/feed/` RSS endpoint is unreliable (serves a ~5-year-stale cached comments feed on
  most requests) — deliberately not used anywhere in this actor.
- Only ~6 articles sampled in depth (News/Business, Sport, Education, Metro, one empty-title
  edge case, one invented-slug 404 probe). A live-blog, video-feature, or photo-gallery template,
  if this site has one, was not sampled.
- `date`/`date_gmt`/`modified`/`modified_gmt` are passed through exactly as WordPress emits them —
  `date`/`modified` have no timezone suffix but are 1 hour ahead of their `_gmt` twins, consistent
  with WAT (West Africa Time, UTC+1). Don't assume `date` is UTC.

## Diff cadence

Quarterly smoke test recommended.
