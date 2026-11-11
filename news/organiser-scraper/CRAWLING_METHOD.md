# Crawling Method — Organiser

**Last verified:** 2026-08-26

Organiser (`organiser.org`) is an English-language weekly news magazine
published by the Rashtriya Swayamsevak Sangh (RSS), India. Despite the
weekly print cadence, the `organiser.org` website itself publishes many
articles per day.

## Robots.txt

```
User-agent: *
Disallow: /administrator/
Disallow: /cache/
Disallow: /components/
Disallow: /images/
Disallow: /includes/
Disallow: /installation/
Disallow: /language/
Disallow: /libraries/
Disallow: /media/
Disallow: /modules/
Disallow: /plugins/
Disallow: /templates/
Disallow: /tmp/
Disallow: /xmlrpc/
Disallow: /wp-admin/

Sitemap: https://organiser.org/lotus-news-sitemap.xml
Sitemap: https://organiser.org/sitemap_index.xml
```

A legacy Joomla-style directive set (`/administrator/`, `/components/`,
`/templates/`, `/libraries/`, `/modules/`, `/plugins/`, `/cache/`,
`/installation/`, `/language/` — none of which exist on the site today,
which runs WordPress) plus two real WordPress paths (`/wp-admin/`,
`/xmlrpc/`), all under one `User-agent: *` group.

**Verified clean on both required checks:**
- No `Disallow: /` (no blanket block), and no
  Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai/
  GPTBot/CCBot disallow line of any kind.
- No plain-English natural-language prohibition against AI/LLM
  training/scraping anywhere in the file (read in full, not just parsed
  directives) — unlike the Star Malaysia case that prompted this extra
  screening step, there is no comment block or notice text at all here.

Fetched twice (plain `curl` UA and `curl_cffi chrome124`) with identical
results — confirmed crawlable.

## WAF

`organiser.org` sits behind **Cloudflare** (`server: cloudflare`, `cf-ray`
present on every response) but presents **no active challenge** to plain
`curl_cffi chrome124` impersonation, and even a bare UA-only `curl` gets a
clean 200 on the homepage, article pages, `/feed/`, and the news sitemap —
no "Just a moment"/challenge-platform/captcha body markers on any path
tried. Real HTTP 404s are served as expected for invented article slugs
(no soft-404-to-homepage quirk, unlike Premium Times / Punch in this
portfolio).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://organiser.org/<yyyy>/<mm>/<dd>/<id>/<section>/<slug>/`

The page emits **one** `<script type="application/ld+json">` block — a
Rank-Math-style `@graph` array of 7 cross-referenced nodes: `NewsArticle`,
`WebPage`, `ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`,
`Person`.

The `NewsArticle` node carries `headline`, `datePublished`, `wordCount`,
`keywords`, `articleSection` (list, e.g. `["Politics", "Bharat", "RSS
News", ...]`), `thumbnailUrl`, `inLanguage` — but **no `articleBody`** and
**no `dateModified`** (confirmed absent, not just omitted, on every sampled
article).

**`author` and `publisher` are always bare `{"@id": "..."}` references**
that must be resolved against the sibling `Person`/`Organization` nodes in
the same `@graph` array — same pattern as `premiumtimes-scraper`. The
`Organization` node's `name` is always `"Organiser"`.

**Quirk — `keywords` is a JSON *object*, not an array.** Instead of
`["kw1", "kw2", ...]`, the raw JSON-LD carries something like
`{"2": "RSS", "3": "BJP Leader CT Ravi", "4": "...", "5": "..."}` — sparse,
non-contiguous string-integer keys (the first index observed varies: `"0"`
on one sample, `"2"` on another). This looks like a PHP associative array
(with some numeric indices removed/reordered) serialized straight to JSON
by the SEO plugin. Confirmed on 2 independent article samples, both
non-list. Passed through as-is (raw passthrough per portfolio convention) —
not reshaped into a list, since guessing at the "right" order would corrupt
data.

Full body text comes from HTML: `div.entry-content > div.content-inner`
(JNews/Jeg WordPress theme — `article.jeg_post` wraps the whole page),
**direct-child `<p>` tags only** (`recursive=False`). Confirmed the
container is present and non-empty on both sampled articles (18 and 63
paragraphs respectively). Ad slots (`div.jeg_ad...`), inline embeds, and
share widgets are sibling `<div>` elements at that same level, not `<p>`
tags, so the `recursive=False` scan for `<p>` excludes them automatically
with no denylist needed.

`description` is pulled from `<meta name="description">` (falls back to
the `WebPage` node's own `description` field if the meta tag is ever
missing — not observed missing on any sample).

`image` is resolved from the `ImageObject` node referenced by
`NewsArticle.image` (a bare `{"@id": ...}` ref, same pattern as
author/publisher) — its `url` field.

### 2. Latest headlines — `S2-rss`

`GET https://organiser.org/feed/`

Standard WordPress feed, but richer than RSS 2.0 minimum: `title`, `link`,
`guid` (`https://organiser.org/?p=<id>`), `pubDate`, `dc:creator`
(byline, findable as `creator` after BeautifulSoup's `xml` parser strips
namespace prefixes), `category` (**list** — many WordPress category+tag
values per item, e.g. `["Bharat", "Analysis", "MGNREGA", "Rural
Development", ..., "FEATURED", "MAIN", "India"]`), `description` (HTML:
lead `<img>` + teaser paragraph), and `content:encoded` (findable as
`encoded`) — **full article body as HTML**, confirmed ~1.4x longer than
`description` on a direct length comparison (11,973 vs 7,518 chars on one
sample; 10,300 chars of actual `<p>` text after tag-stripping). So `latest`
mode already returns full article text via `contentEncoded`, not just a
teaser — matching `newindianexpress-scraper`'s pattern more than
`premiumtimes-scraper`'s bare-headline one.

**Quirk — `?paged=N` does NOT paginate.** Unlike `premiumtimes-scraper`
(where `/feed?paged=2` genuinely advances), `organiser.org/feed/?paged=2`
returns HTTP 200 but the **byte-identical first page again** — confirmed
by fetching both and diffing: same 10 `guid`s in the same order on both
"pages". `/feed/page/2/` returns 200 with no `<item>` elements at all;
`/page/2/feed/` 404s. No working pagination path was found for this feed.
As a result, `latest` mode makes a **single** fetch and is capped at the
feed's natural page size (**10 items**) — `limit` in the input schema is
capped at 10 accordingly, rather than silently under-delivering on a
higher requested limit.

The `lotus-news-sitemap.xml` referenced in `robots.txt` was also checked
and confirmed live (title/pubDate per URL, updates multiple times/hour) —
a viable `S3` fallback for higher-volume `latest` coverage if the 10-item
cap ever becomes a real requirement, not wired up here to keep the actor
simple.

## Paywall behavior

None observed. No `isAccessibleForFree`/`hasPart` schema markers, no
truncated `articleBody`, no "subscribe to continue" text on either sampled
article. Organiser is a free, open-access site.

## Known limits

- `latest` mode is capped at 10 items per run (the feed's natural page
  size — see pagination quirk above). Use `mode: "article"` with a list of
  URLs (e.g. pulled from the news sitemap) if more than 10 are needed in
  one run.
- `dateModified` is never populated in the JSON-LD on any sampled article
  — passed through as `None`/absent rather than fabricated.
- `keywords` (article-mode) is a raw JSON object with sparse
  string-integer keys, not a list — see Quirk above. Downstream consumers
  wanting a flat list should sort by key and take `.values()` themselves.
- 404s for invented article slugs are real HTTP 404s — no soft-404 quirk
  observed, unlike some other WordPress sites in this portfolio.
- Only 2 articles sampled in depth (both "Bharat" section). A structurally
  different template (opinion/editorial, photo-gallery, video feature) was
  not sampled.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the ld+json `@graph` still resolves a `NewsArticle`
node and `div.entry-content > div.content-inner` still yields non-empty
paragraphs. If Organiser redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
