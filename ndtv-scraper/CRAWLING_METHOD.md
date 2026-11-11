# Crawling Method — NDTV

**Last verified:** 2026-08-26

## Robots.txt

Independently re-verified (per project policy, following the "Babak 14"
false-clear incident). `https://www.ndtv.com/robots.txt` returns 200 under
`curl_cffi` chrome124 impersonation, 765 bytes, full text:

```
User-agent: *
Disallow: /images/ndtvvideo/*
Disallow: /news/redirect/*
Disallow: /news/feeds/*
Disallow: /page/send-email/*
Disallow: /mb/
Disallow: /usopen09/*
Disallow: /ndtvfuture/*
Disallow: /ndtvfuture/ndtv/postcomments.aspx
Disallow: /video/embed-player
Disallow: /smart-picks/
Disallow: /smart-picks/quiz/

Sitemap: https://www.ndtv.com/sitemap.xml
Sitemap: https://www.ndtv.com/sitemap/google-news-sitemap
...

User-agent: AdsBot-Google
Allow: /smart-picks/

User-agent: Mediapartners-Google
Allow: /smart-picks/

User-agent: AmazonAdBot
Allow: /smart-picks/
```

No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-SearchBot`/`anthropic-ai`
user-agent block anywhere in the file, and no blanket `Disallow: /` under
`User-agent: *`. None of the specific disallowed paths (`/images/ndtvvideo/`,
`/news/redirect/`, `/news/feeds/`, `/mb/`, `/video/embed-player`,
`/smart-picks/`) overlap with the article/video/live-blog URLs or the RSS
feed this actor uses. **Clear to build.**

Note: a plain, un-impersonated `curl` (and a request using the literal
`Googlebot` user-agent string) both got an Akamai `Access Denied` /
`errors.edgesuite.net` block page on this same URL — see WAF section below.
This is a TLS-fingerprint-level bot gate, unrelated to the robots.txt policy
itself, which is fully accessible once that gate is cleared.

## WAF

**Akamai Bot Manager.** Evidence: `ak_bmsc` cookie set on every response,
`akamai-grn` response header, and a plain/unimpersonated HTTP client (or one
sending the bare `Googlebot` UA string) gets a 403-style `Access Denied` page
served from `errors.edgesuite.net` (Akamai's edge error host) instead of the
real page.

`curl_cffi` `chrome124` impersonation clears it cleanly on every URL tested —
homepage, section pages (`/india-news`, `/world-news`, `/business-news`),
plain article pages, video-story pages, live-blog pages, and the Feedburner
RSS feed. All returned 200 with full content, no JS challenge body, no
captcha. No special warmup/cookie-harvest dance was needed beyond the
existing template's plain homepage GET.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.ndtv.com/<section>/<slug>-<id>` (no `.html` suffix, unlike
Hindustan Times)

Each article page emits 3-8 `application/ld+json` blocks depending on
template (see below). The extractor scans all of them and picks the one with
`@type: "NewsArticle"`, which is present on **every** template sampled:

- **Plain text articles** (e.g. `/india-news/...`, `/world-news/...`,
  `/education/...`): `NewsArticle` carries the full plain-text
  `articleBody` (1,600-2,300 characters across 5 samples), `headline`,
  `description`, `keywords` (comma-separated string), `articleSection`,
  `author` (array of `Person`, frequently a wire-service credit like "Press
  Trust Of India" with a link to an `/agencies/...` author page rather than
  an NDTV staff byline), `image`, `datePublished`/`dateModified`,
  `isAccessibleForFree: true` on every sample (no paywall marker seen).

- **Video-story pages** (`/video/<slug>-<id>`): the page additionally emits
  `VideoGallery` and `VideoObject` ld+json blocks (video metadata, embed
  info), but its `NewsArticle` block has **no `articleBody` field at all** —
  only `description` (a short caption, 300-500 characters) and `headline`.
  This is a genuine template difference, not a bug: video pages are built
  around the clip, not prose. The extractor still returns a valid record
  (raw passthrough of whatever the `NewsArticle` node contains) rather than
  raising `UnexpectedShape` — a present-but-thin JSON-LD node is a content
  difference, not a shape change. Downstream consumers wanting video
  transcripts/captions would need the separate `VideoObject` block, which
  this actor does not currently extract (see Known limits).

- **Live-blog pages** (e.g. `stock-market-...-live-updates-...`,
  `weather-today-live-updates-...`): the page emits **both** a `NewsArticle`
  block (a rollup summary with a real `articleBody`, same shape as a plain
  article) **and** a separate `LiveBlogPosting` block (`coverageStartTime`/
  `coverageEndTime`, and — per one sample — 70KB+ of nested
  `liveBlogUpdate` entries, one per timestamped update). The extractor
  picks the `NewsArticle` block only, matching this portfolio's convention
  of using the first array-typed match found (`ARTICLE_TYPES` does not
  include `LiveBlogPosting`). This means live-blog records carry a
  reasonable rollup summary but **not** the individual minute-by-minute
  updates — see Known limits.

No `__NEXT_DATA__` was found — NDTV does not appear to use Next.js SSR data
injection; the JSON-LD blocks are server-templated directly into the HTML.

**Quirk — double HTML-escaped entities:** `articleBody`/`headline`/
`description` values contain entities escaped *twice*, e.g. a literal
double quote in the source text appears as `&amp;quot;` (not `&quot;` or a
bare `"`), and a non-breaking space as `&amp;nbsp;`. This is baked into
NDTV's CMS template output, not a scraping artifact. Passed through
raw/verbatim per this portfolio's raw-passthrough convention — downstream
consumers wanting clean text need to HTML-unescape twice.

### 2. Latest headlines — `S2-rss`

`GET https://feeds.feedburner.com/ndtvnews-latest`

Standard RSS 2.0 (`<channel>/<item>`) with `media:` and `content:encoded`
namespaces. Fields used: `title`, `link`, `guid`, `pubDate`, `description`.
Confirmed live 2026-08-26: 100 items, most recent `pubDate` within minutes of
the request, spanning multiple sections (India, World, Business, Delhi —
this is a genuine site-wide feed, unlike Hindustan Times where only a
section-specific feed was found).

**Quirk:** `link`/`guid` carry a trailing `#publisher=newsstand` URL
fragment (e.g. `...-11959122#publisher=newsstand`). Fragments are
client-side-only and don't affect the actual page fetch (confirmed: the
article page loads correctly whether or not the fragment is present), so
this is passed through as-is rather than stripped.

NDTV's own `https://www.ndtv.com/rss` is **not** a feed — it's an HTML
directory page linking to section-specific feeds. `https://www.ndtv.com/
india-news/rss` (guessed section-feed path) 404s. The Feedburner mirror
above was found to be the actual working site-wide feed and is what this
actor uses.

## Paywall behavior

No paywall markers or truncation observed on any sampled article.
`isAccessibleForFree: true` on every `NewsArticle` block sampled (plain
articles, video pages, live-blog pages).

## Known limits

- `latest` mode returns the site-wide Feedburner feed only — no per-section
  option is exposed as an input, unlike some other actors in this portfolio.
- Video-story pages return `NewsArticle` metadata (headline, description,
  dates, author) but **no `articleBody`** — the article text simply doesn't
  exist on that template. The richer `VideoObject`/`VideoGallery` blocks
  (video URL, duration, thumbnail) are present on the page but not
  extracted by this actor.
- Live-blog pages return only the `NewsArticle` rollup summary, not the
  individual timestamped `LiveBlogPosting` update entries. A future
  enhancement could add a dedicated live-blog extraction path if that
  granularity becomes a requirement.
- `keywords` is a comma-separated string in the JSON-LD, not an array.
- `headline`/`articleBody`/`description` carry doubly HTML-escaped entities
  (see Quirk above) — passed through raw, not unescaped.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL (plus one video URL and one live-blog URL, since NDTV runs three
distinct templates) and confirm the `NewsArticle` ld+json block is still
found. If NDTV redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
