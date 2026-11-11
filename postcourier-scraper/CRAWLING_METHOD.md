# Crawling Method — Post Courier (PNG)

**Last verified:** 2026-08-26

## WAF

`postcourier.com.pg` shows **no active WAF challenge**. `curl_cffi`
`chrome124` gets a clean 200 on the homepage, article pages, the WordPress
REST API, and the RSS feed. `robots.txt` is a standard WordPress/Yoast/
WooCommerce file: a top block disallowing only `/wp-content/uploads/
wc-logs/`, `/wp-content/uploads/woocommerce_transient_files/`,
`/wp-content/uploads/woocommerce_uploads/`, `?add-to-cart=` query strings,
and `/wp-admin/` (with `/wp-admin/admin-ajax.php` explicitly re-allowed),
plus a separate "START YOAST BLOCK" section that is a blanket
`User-agent: * / Disallow:` (allow-all). No Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai/GPTBot disallow directive
anywhere, and no plain-English prohibition against AI/LLM training or
scraping in any comment. Independently re-fetched and confirmed on this
pass (2026-08-26).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. Not required to clear any block on this target -- kept for
consistency and future-proofing.

## Data sources

### 1. Article pages — `S1-jsonld+wpapi`

`GET https://www.postcourier.com.pg/<slug>/`

Post Courier runs WordPress + Yoast SEO + WooCommerce Memberships. Each
article page emits one `<script type="application/ld+json">` block, a
Yoast-style `@graph` array of cross-referenced nodes (`Article`, `WebPage`,
`ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`, `Person`). The
`Article` node carries `headline`, `datePublished`, `dateModified`,
`wordCount`, `keywords`, `articleSection`, `thumbnailUrl` — but no
`articleBody`. `author` shape is inconsistent across samples (sometimes a
list of `{"@id": ...}` refs, sometimes a single inline dict) —
`_resolve_refs` in `extractor.py` normalizes both. `publisher` is a bare
`{"@id": "...#organization"}` ref resolved against the same graph to
`"Post Courier"`.

Full body text and paywall status come from the WordPress REST API
instead of HTML scraping:

`GET https://www.postcourier.com.pg/wp-json/wp/v2/posts?slug=<slug>&_embed=1`

Returns `content.rendered` (an HTML fragment) plus embedded author name,
featured-media URL, and category/tag term names via `_embedded`.

**Hard paywall (WooCommerce Memberships), re-confirmed live on this pass:**
a paywalled post's `content.rendered` contains only a `div.content-preview`
teaser (~2 paragraphs) followed by a
`div.wc-memberships-restriction-message` upsell block instead of the real
body. Detected by that CSS class string; when present, `articleBody` is
limited to the paragraphs inside `div.content-preview` and `_paywalled` is
set `True`. Free articles have no such wrapper — every `<p>` in
`content.rendered` is used and `_paywalled` is `False`.

Sampled live during this verification pass:
- `air-niugini-handles-major-b747-freighter-operation-in-port-moresby`
  (PNG News) — paywalled, truncated to 2 paragraphs.
- `solomon-islands-high-court-rules-2023-pacific-games-spending-illegal`
  (PNG News/World, tagged `#Pacific NEWS`) — paywalled.
- `222m-pacific-games-spending-bombshell` (World/World News, tagged
  `PacificNews`/`pacnews`) — **free**, full ~619-word body returned.
- A deliberately-invented slug returns a **real HTTP 404** on the article
  HTML page — no soft-404 quirk observed, confirmed again on this pass.

A genuine upstream authoring quirk reconfirmed live: some article text
uses the same left-curly-quote character (U+201C) for both the opening
AND closing quote mark around a phrase (e.g. `"serious"` renders with
both marks as `"` in `222m-pacific-games-spending-bombshell`'s body) —
passed through verbatim per the raw-passthrough convention, not corrected.

No `<meta name="description">` tag was found on any sampled article page,
and the graph's `WebPage` node carries no `description` field either —
`description` falls back to `<meta property="og:description">`, populated
on every sample.

### 2. Latest headlines — `S2-rss`

`GET https://www.postcourier.com.pg/feed/`

Standard WordPress RSS2 feed, live and populated — confirmed HTTP 200 with
10 `<item>` elements on this pass (WordPress' default feed page size; there
is no `?paged=` or count parameter that reliably raises this past 10, so
`latest` mode's practical ceiling is the feed's own page size even though
the input schema advertises up to 100). Each `<item>` carries `title`,
`link`, `pubDate` (real per-article RFC-822 timestamp), `dc:creator`, and
one or more `<category>` tags. Confirmed already newest-first in feed
order; sorted descending by parsed `pubDate` defensively anyway.

Unlike some smaller regional-daily actors in this portfolio where RSS/
sitemap is broken and a homepage-link-scrape fallback is required, that
fallback is **not** needed here — the feed is healthy.

## Paywall behavior

Real and pervasive. Of the 10 most-recent posts (via RSS) and the 30 most
recent posts (via the WP REST API, unfiltered), **all were paywalled** at
verification time — every one tagged "PNG News". Filtering the WP REST API
to the "World" category (id `80770`) instead showed the opposite: 14 of 15
recent posts in that category were **free** (`_paywalled: False`). This
matches the pattern documented in `constants.py`: PNG-local news
(PNG News/Business/Sports) is gated behind WooCommerce Memberships; wire-
service/regional PACNEWS content tagged "World"/"World News" is
frequently free. Because the RSS feed itself carries no category filter
and only returns the 10 newest posts overall, `latest` mode's output on
any given run will likely be dominated by paywalled PNG-local stories
unless the newest 10 happen to include World-tagged wire content.

## Known limits

- `latest` mode is capped at the RSS feed's own page size (10 items
  observed) regardless of the `limit` input field's stated max of 100 —
  requesting more than the feed provides simply returns fewer records than
  asked, not an error.
- The RSS feed carries no per-item paywall indicator — a consumer must
  fetch each `link` in `article` mode to find out `_paywalled` status.
- Only a handful of articles sampled in depth. A structurally different
  page type (live-blog, photo gallery, video) was not sampled and might
  lack the Yoast `@graph` block entirely or have a differently-shaped
  `content.rendered` — would raise `UnexpectedShape` rather than silently
  emit a wrong or empty record.
- `coauthors` is passed through as raw unresolved Co-Authors Plus term IDs
  (e.g. `[84253]`) — no name resolution attempted, per raw-passthrough
  convention.

## Diff cadence

Quarterly smoke test recommended.
