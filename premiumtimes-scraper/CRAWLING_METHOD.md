# Crawling Method — Premium Times Nigeria

**Last verified:** 2026-08-26

## WAF

`premiumtimesng.com` sits behind **Cloudflare** (`server: cloudflare`, `cf-ray`
present) but shows **no active JA3/TLS-fingerprint challenge** for normal
traffic. `curl_cffi` `chrome124` gets a clean 200 on the homepage (~850 KB),
article pages (~440 KB), `/feed`, and `/feed?paged=N` -- no "Just a
moment..." interstitial, no `cf-mitigated` header.

`robots.txt` is a stock Yoast SEO block:

```
User-agent: *
Disallow:

crawl-delay: 10

Sitemap: https://www.premiumtimesng.com/sitemap_index.xml
```

A single `Disallow:` with no path (allow-all) under one `User-agent: *`
group -- no Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai disallow anywhere, and only one user-agent group total, so the
multi-group-parser trap documented elsewhere in this portfolio doesn't
apply here.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. The full profile ladder (`chrome116`, `chrome99_android`,
`safari17_0`, `edge101`, `firefox133`, `safari18_0`) was also run against a
blocked-looking response during recon (see below) -- every profile hit the
*identical* response, which is what confirmed the block was not a
TLS/JA3 gate.

### Quirk found: stale edge-cached JS challenge on individual article URLs

One specific article URL, on first fetch during recon, returned a small
(~1.6 KB) HTML page instead of the real article:

```html
<html><body>.....<script type="text/javascript" src="/aes.js"></script>
<script>var _0xc43a=[...]; ... slowAES.decrypt(...) ...
document.cookie = "TZTC=" + toHex(...) + "; expires=...; path=/";
document.location.href = "<same-url>?tztc=1";</script>...
```

This is an old-style Cloudflare JS cookie-setter challenge (`TZTC` cookie,
`slowAES`-based). Diagnosis:

- **Not a TLS/JA3 block** -- all 7 profiles in the ladder returned the
  *exact same* 1592-byte body for that URL.
- **Not IP-reputation** -- fetching a different, never-before-requested
  article URL immediately returned the real ~440 KB page on the very
  first attempt, from the same IP, same session.
- **It's a stale edge cache artifact** -- the challenge response itself
  carried `cf-cache-status: HIT` and persisted across repeated refetches
  of that same URL well past its own advertised `max-age=120`. Appending
  a cache-busting query parameter (`?_cb=1`) forced a cache MISS and
  immediately returned the real page (200, 443 KB, `cf-cache-status: MISS`),
  confirming the origin serves real content fine -- only the edge cache
  entry for that exact URL was stuck serving an old challenge response
  (most likely a previous bot-flagged visitor's challenge got cached and
  is being replayed to everyone hitting that URL until the cache entry is
  purged or expires by Cloudflare's own edge TTL, which can exceed the
  advertised browser `max-age`).

**Mitigation implemented in `src/client.py`:** `is_blocked()` treats
`slowAES` / `TZTC=` in the response body as a block signal (alongside the
usual 403/429/503 and generic WAF markers). On a detected block, the retry
loop does **not** just re-request the same URL -- it appends/refreshes a
`_ptscb=<n>` cache-busting query parameter before retrying, since a plain
retry against the identical URL would keep hitting the same stale cache
entry. Confirmed working: the retry successfully retrieved a previously
observed stuck-challenge URL later in the session.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.premiumtimesng.com/<category-path>/<numeric-id>-<slug>.html`

(`<category-path>` varies in depth: `opinion/`, `news/top-news/`,
`news/more-news/`, `business/business-news/`, `investigationspecial-reports/`,
`features-and-interviews/`, `regional/north-central/`, `promoted/`, etc. --
all share the same template.)

The page emits **one** `<script type="application/ld+json"
class="yoast-schema-graph">` block -- a Yoast-SEO-style `@graph` array of
7 cross-referenced nodes: `Article` (not `NewsArticle`), `WebPage`,
`ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`, `Person`.

The `Article` node carries `headline`, `datePublished`, `wordCount`,
`commentCount`, `keywords`, `articleSection` (e.g. `["Contributors",
"Opinion"]`), `thumbnailUrl` -- but **no `articleBody`**, and its `author`
and `publisher` fields are `{"@id": "..."}` references, not inline
objects. The extractor builds an `@id -> node` index of the whole
`@graph` and resolves:

- `author` -> the referenced `Person` node's `name` (byline, e.g.
  `"Samuel Aruwan"`)
- `publisher` -> the referenced `Organization` node's `name` (always
  `"Premium Times"` on every sample, resolved dynamically rather than
  hardcoded)

**No `dateModified` field exists anywhere in the schema graph** -- checked
across all sampled articles (opinion, news/top-news, news/more-news,
business), confirmed genuinely absent, not just omitted by the extractor.

**WordPress double-HTML-escapes text values inside this JSON** -- e.g. the
`headline` value for the Sultan Abubakar piece is the literal JSON string
`"Sultan Sa&#8217;ad Abubakar III at 70..."`, not real Unicode. `json.loads`
does not decode HTML entities inside string values, so `html.unescape()` is
applied to every text value pulled from the graph (`headline`, `keywords`,
`articleSection` entries, resolved `author`/`publisher` names). HTML-parsed
text (the article body, meta tags) does **not** need this treatment --
BeautifulSoup already decodes entities when walking the DOM.

Full body text comes from HTML: `div.entry-content > div.content-inner`,
**direct-child `<p>` tags only** (`recursive=False`). Confirmed clean
(no ad/promo text leaking into `articleBody`) on 3 samples spanning opinion,
news/top-news, and business/business-news templates (20–37 real paragraphs
each). Everything else at that DOM level is a sibling, non-`<p>` element,
so it's excluded automatically without a denylist:

- `div.jeg_share_button` -- floating share bar (empty)
- `div.code-block-N` -- ad slots / "Join our WhatsApp Community" /
  "Follow us on Google News" promo inserts (theme: Jannah/`jeg_` prefix)
- `div.ai-viewports` -- Ad Inserter plugin ad slots
- `figure.wp-caption` -- lead/inline image + caption
- `div.at-below-post` / `div.sharedaddy` -- share-this widget
- `div.wp-block-group` -- "Discover more from Premium Times Nigeria"
  email-subscribe box
- `div.jeg_post_tags` -- tag pills

One direct-child `<p>` that **is** kept (correctly, as real content): a
trailing author-bio line (e.g. `"Samuel Aruwan is a postgraduate student
at Ahmadu Bello University, Zaria."`) -- standard practice for
opinion/contributor pieces, not boilerplate to filter.

`description` is pulled from `<meta name="description">`, falling back to
the ld+json `WebPage` node's own `description` field if the meta tag is
missing. Both were confirmed present on 2 of 3 samples; the opinion piece
(`905169`) genuinely has neither -- verified directly (not an extractor
bug) -- so `description` is treated as best-effort, not raised on if
absent.

### 2. Latest headlines — `S2-rss`

`GET https://www.premiumtimesng.com/feed` (optionally `?paged=N` for more)

Standard WordPress default feed (`generator: https://wordpress.org/?v=6.9.7`,
`content-type: application/rss+xml`). Returns exactly **15 items per page**,
confirmed paginable via `?paged=2`, `?paged=3`, etc. with no overlap/
duplication between pages (checked guids across 5 consecutive pages). No
`content:encoded` full-text field -- `latest` mode is teaser-only by
design; use `article` mode against the `link` for full text. The actor's
`fetch_latest()` walks `?paged=N` automatically until it has enough items
for the requested `limit` (max 50, i.e. up to 4 pages), deduping by `guid`.

Fields: `title`, `link`, `dc:creator` (byline), `category` (repeatable --
Premium Times mixes section names and freeform tags in the same
`<category>` elements, e.g. `["More News", "ABORNE", "Fraud", ...]`),
`guid` (`?p=<id>`, matches the numeric ID in the article URL), `pubDate`,
and `description`.

`description` is raw, **once**-HTML-escaped HTML content inside a CDATA
block -- a lead `<img src="...">` tag, a teaser `<p>`, and a literal
`"The post &lt;a&gt;Title&lt;/a&gt; appeared first on &lt;a&gt;Premium
Times Nigeria&lt;/a&gt;."` boilerplate suffix (same pattern documented in
`vice-scraper`'s recon). There is **no `<enclosure>` tag** on this feed
(unlike `kyivpost-scraper`), so the lead image is instead pulled out of
that embedded `<img src="...">` before the HTML tags are stripped. The
cleaned `description` keeps the "appeared first on..." boilerplate text
as-is -- it's real feed content, not noise, matching the `vice-scraper`
convention.

The Google News-style `sitemap_index.xml` -> `post-sitemap.xml` (+
20-odd dated archive sitemaps, oldest dated 2012) was also confirmed
present and working, and would be a viable fallback, but `/feed` was
chosen as the primary `latest`-mode source since it carries richer fields
(author, categories, description, image) in one request and supports easy
pagination for the `limit` up to 50.

## Paywall behavior

None observed. No "subscribe"/"paywall"/"premium"/"member-only" markers
found in raw HTML on any sampled page. Premium Times is a free,
open-access site.

## Known limits

- `description` in `article` mode is occasionally absent (neither the meta
  tag nor the ld+json `WebPage.description` is populated) -- confirmed on
  1 of 3 sampled articles, an opinion piece. Not an extraction bug.
- 404s for deleted/never-existed article IDs are **soft-404s**, not real
  HTTP 404s: the server returns `HTTP 200` with the **homepage's own HTML**
  (same title, same size, no `Article`/`NewsArticle` node in the schema
  graph, `<link rel="canonical">` pointing at the homepage instead of the
  requested URL). The extractor detects this by checking for an absent
  `Article` node in the `@graph` and raises `ArticleNotFound`, which
  `main.py` converts to a normal `_error: "not_found"` record -- exactly
  like a real 404 from the caller's point of view.
- A completely malformed/nonsensical path (not matching the
  `/<category>/<id>-<slug>.html` shape at all) can return an HTTP 502 from
  Cloudflare rather than either a real 404 or the homepage soft-404 --
  treated as a normal transient/retryable HTTP error (`_error: "http_502"`
  if retries are exhausted), not specifically handled as not-found.
- A stale Cloudflare edge-cached JS challenge can intermittently stick to
  individual article URLs (see WAF section above) -- mitigated via
  cache-busting query param on retry, but if Cloudflare ever serves this
  challenge as a **fresh** (non-cached) response instead of a stale hit,
  that would indicate a real anti-bot escalation and should be
  re-triaged (not yet observed).
- Only 3 articles sampled in depth (1 opinion, 2 news/business), plus the
  RSS feed and a soft-404/502 probe. A structurally different template
  (e.g. a live-blog, video feature, or photo-gallery page) was not
  sampled.

## Diff cadence

Quarterly smoke test recommended.
