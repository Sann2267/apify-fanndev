# Crawling Method — Punch Nigeria

**Last verified:** 2026-08-26

## Robots.txt

```
# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:

Sitemap: https://punchng.com/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

Stock Yoast SEO block: a single `Disallow:` with no path (allow-all) under
one `User-agent: *` group. No Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai disallow anywhere, and only one user-agent
group total (no multi-group-parser trap). Independently re-verified with a
fresh `curl_cffi` fetch during this build (`GET
https://punchng.com/robots.txt` -> HTTP 200, body as above) — confirmed
crawlable.

## WAF

`punchng.com` sits behind **Cloudflare** (`server: cloudflare`, `cf-ray`
present) but shows **no active JA3/TLS-fingerprint challenge** for normal
traffic. `curl_cffi` `chrome124` gets a clean 200 on the homepage (~384 KB),
article pages (~230 KB), and `/feed` (~36 KB) — no "Just a moment..."
interstitial, no `cf-mitigated` header, no challenge body. No stale-edge-
cache quirk (the one found on premiumtimesng.com) was observed on any of
the 5 article URLs sampled during recon.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://punchng.com/<slug>/`

The page emits **one** `<script type="application/ld+json"
class="yoast-schema-graph">` block — a Yoast-SEO-style `@graph` array of 6
cross-referenced nodes: `NewsArticle`, `WebPage`, `ImageObject`,
`BreadcrumbList`, `WebSite`, `Person`.

The `NewsArticle` node carries `headline`, `datePublished`, `dateModified`,
`wordCount`, `keywords`, `articleSection` (e.g. `["Business & Economy"]`),
`thumbnailUrl` — but **no `articleBody`**.

**Unlike Premium Times / Ghana Web, `author` is an inline object, not a
bare `{"@id": ...}` reference** — e.g. `"author":{"name":"Ayoola
Babalola","@id":"https://punchng.com/#/schema/person/6c2d0..."}`. The
extractor still runs the name through the same `@id`-resolving helper used
elsewhere in the portfolio (for robustness against a future shape change),
but no round-trip through the graph's `Person` node is strictly required —
the name is already present on the `author` field itself. Confirmed
consistent across 4 sampled articles (News/Business, Opinion/Columns, Metro
Plus).

**There is no `Organization`/`publisher` node anywhere in the graph on this
site** — confirmed absent on every sampled article. Instead, `publisher` is
read from `<meta property="og:site_name">` (`"Punch Newspapers"`), which is
real page content (also present in `article:publisher` as a Facebook page
URL, and `twitter:site` as `@mobilepunch`, neither of which is a better fit
for a publisher name).

**WordPress double-HTML-escapes text values inside this JSON** — e.g. the
`articleSection` value for the tariffs piece is the literal JSON string
`"Business &amp; Economy"`, not a real `&`. `html.unescape()` is applied to
every text value pulled from the graph (`headline`, `keywords`,
`articleSection`, resolved author names). HTML-parsed text (the article
body, meta tags) does **not** need this treatment — BeautifulSoup already
decodes entities when walking the DOM.

Full body text comes from HTML: `article.single-article div.post-content`,
**direct-child `<p>` tags only** (`recursive=False`). This exact selector
(with the `article.single-article` ancestor scope) is required because
`div.post-content` alone matches **10 elements** on a typical article
page — one is the real article body, the other 9 are related-article
teaser cards elsewhere on the page that also carry the bare
`post-content` class. Confirmed clean (direct-child `<p>` count equals
total descendant `<p>` count, i.e. no nested wrapper divs leaking extra
paragraphs) on 3 samples spanning News/Business (20 paragraphs), Opinion/
Columns (38 paragraphs), and Metro Plus (18 paragraphs).

`description` is pulled from `<meta name="description">`, falling back to
the ld+json `WebPage` node's own `description` field if the meta tag is
ever missing (not observed missing on any of the 4 samples).

### 2. Latest headlines — `S2-rss`

`GET https://punchng.com/feed`

Served from a custom aggregator (`rss.punchng.com`, mirrored at
`punchng.com/feed`; `<generator>https://rss.punchng.com</generator>`), not
a stock WordPress `/feed` — no `?paged=N` pagination support was found (a
single request returns a fixed batch, ~36 KB / dozens of items; `limit` in
this actor is applied by slicing the single response, not by paginating).

Fields observed: `title`, `link` (carries `?utm_source=rss.punchng.com&
utm_medium=web` tracking params, passed through raw — real feed content,
not stripped), `pubDate`, `dc:creator` (constant `"Punch Newspapers"` on
every sampled item — **not** a real per-article byline; use `article` mode
against `link` for the real author), `<category>` (always an empty CDATA
block on every sampled item), `guid` (identical to `link`), and a teaser
`description` (plain text inside CDATA with a trailing `"Read More:
<url>"` line — kept as real feed content, not stripped as boilerplate).

Every sampled item shares the **exact same** `<enclosure>` URL — the Punch
masthead logo (`punch-logo-500x179-1.png`), not a per-article lead image.
Passed through as `enclosureUrl` since it's genuine feed content, but
documented in the output schema as unreliable for a real thumbnail — use
`article` mode's `thumbnailUrl` instead.

The Yoast `sitemap_index.xml` was also confirmed present
(`https://punchng.com/sitemap_index.xml`, referenced from robots.txt) and
would be a viable fallback `latest`-mode source, but `/feed` was chosen as
primary since it needs no extra request to discover sub-sitemaps and
returns a large-enough batch (dozens of items) for the `limit` range this
actor supports (max 50).

## Paywall behavior

None observed. No "subscribe"/"paywall"/"premium"/"member-only" markers
found gating article content in raw HTML on any sampled page — the hits
for "subscribe"/"premium" strings are a YouTube channel subscribe button,
the Punch E-Paper (PDF replica) promo link, and a newsletter-signup widget,
none of which block or truncate the article text itself. Punch is a free,
open-access site.

## Known limits

- 404s for deleted/never-existed article slugs are **real HTTP 404s**
  (confirmed on a deliberately-invented slug) — unlike premiumtimesng.com's
  soft-404-to-homepage behavior, no special detection was needed for that
  case here.
- A 200-OK page that isn't an article at all (e.g. `/privacy-policy/`)
  emits a `WebPage`/`CollectionPage` ld+json graph with no `NewsArticle`
  node — detected explicitly and reported as `_error: "not_article"`.
- `/feed` returned no discoverable pagination parameter during recon (no
  `?paged=N` support observed, unlike the stock-WordPress feeds on other
  actors in this portfolio) — `latest` mode is capped by whatever the feed
  returns in one request (well above the actor's own 50-item cap in every
  sample taken).
- RSS `dc:creator` and `<category>` are low-information on this feed
  (constant/always-empty respectively) — `latest` mode is best used to
  discover fresh URLs, then `article` mode for the real byline, section,
  and full text.
- Only 5 articles sampled in depth (News/Business x2, Opinion/Columns,
  Metro Plus, plus one non-article page and one invented-slug 404 probe).
  A structurally different template (e.g. a live-blog, video feature, or
  photo-gallery page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
