# Crawling Method — Kazinform (English edition)

**Last verified:** 2026-08-26

Kazinform is Kazakhstan's state news agency. This is the first Central
Asia outlet added to this portfolio.

## Domain scoping — English edition lives on a separate domain

The flagship domain `inform.kz` (`www.inform.kz`) serves Russian/Kazakh
content; its `robots.txt` only lists Russian-language sitemaps
(`sitemap_index_ru.xml`, `google-news_ru.xml`, `sitemap-last-news-300_ru.xml`).
Following the English-language path from there:

```
https://www.inform.kz/en/  -> 301 -> https://en.inform.kz
https://en.inform.kz       -> 301 -> https://qazinform.com
```

`qazinform.com` ("Qazinform") is confirmed as Kazinform's dedicated
English-edition site (own branding, own layout, `og:locale: en_EN`,
`<html lang="en">`). This actor is scoped **entirely to `qazinform.com`**
— the same pattern as `asharqalawsat-scraper` scoping to the English
subdomain of Asharq Al-Awsat. All article URLs and the latest-headlines
feed used by this actor live on this domain; `inform.kz`/`kaz.inform.kz`
(Russian/Kazakh editions) are out of scope.

## robots.txt / Claude screening

Checked on both editions:

- `https://www.inform.kz/robots.txt` -> HTTP 200:
  ```
  User-agent: *
  Allow: /
  Disallow: /*{{ link }}*
  Disallow: /search/
  Disallow: /*?page=
  Sitemap: https://www.inform.kz/sitemaps/sitemap_index_ru.xml
  Sitemap: https://www.inform.kz/sitemaps/google-news_ru.xml
  Sitemap: https://www.inform.kz/sitemaps/sitemap-last-news-300_ru.xml
  Clean-param: ref /amp/
  ```
  Single `User-agent: *` group, blanket `Allow: /` with only 3 narrow
  functional-path disallows (a templating artifact, `/search/`, and
  paginated query strings). No `Claude`, `ClaudeBot`, `Claude-Web`,
  `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token anywhere, no
  blanket `Disallow: /`. No comments at all in the file, so no
  natural-language AI/LLM-training prohibition either (the Babak-17
  screening layer).

- `https://qazinform.com/robots.txt` -> **HTTP 404** (no robots.txt file
  present on the English-edition domain at all). A missing robots.txt is
  the standard "no crawl restrictions declared" case, not a block — there
  is no file to contain a `Disallow` or a natural-language prohibition.
  Re-checked directly with `curl` (plain, no impersonation) to rule out a
  WAF intercepting the request; got a genuine nginx 404 page
  (`Server: nginx/1.31.3`), not a challenge page.

Conclusion: crawlable on both the mention-domain and the actual
English-edition domain. No machine-readable or natural-language AI
scraping prohibition found on either host.

## WAF

**None found.** `qazinform.com` is served directly by nginx
(`Server: nginx/1.31.3`) — no Cloudflare, no challenge markers. Confirmed
three ways on the same article URL, all returning identical 200 responses
of identical byte size:
- plain `curl` (no TLS impersonation, no browser UA beyond a generic
  `Mozilla/5.0` string)
- `curl_cffi` `impersonate="chrome124"`
- `curl_cffi` `impersonate="chrome131"`

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (retry/warmup scaffolding kept per convention even though nothing
observed requires it).

Note: `en.inform.kz`'s 301 redirect response itself carries Cloudflare
headers (`CF-RAY`, `server: cloudflare`) — that specific redirect hop is
Cloudflare-fronted, but the final destination (`qazinform.com`, where all
actual content and the article/feed requests in this actor land) is not.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://qazinform.com/news/<slug>`

The page emits 2 ld+json blocks: `NewsArticle` and `BreadcrumbList` — the
extractor scans all `<script type="application/ld+json">` tags and picks
the one whose `@type` is `NewsArticle`. That block is **metadata-only**,
matching the `tass-scraper`/`rt-scraper` pattern documented in this
portfolio:

```json
{
  "@type": "NewsArticle",
  "headline": "...",
  "datePublished": "2026-08-26 11:25:00+00:00",
  "dateModified": "2026-08-26 11:25:00+00:00",
  "description": "...",
  "publisher": {"@type": "Organization", "name": "«Inform»", "logo": {...}},
  "image": {"@type": "ImageObject", "url": "..."},
  "speakable": {"@type": "SpeakableSpecification", "cssSelector": ["article-text"]},
  "articleSection": ""
}
```

Quirks observed (consistent across 4 sampled articles):
- **No `articleBody` and no `author` field at all** in the ld+json — both
  come from HTML.
- `publisher.name` is literally `"«Inform»"` — the agency's legacy
  Russian legal name (with guillemets), not `"Qazinform"`/`"Kazinform"`.
  Kept as raw passthrough, not renamed/translated.
- `image` is a single `ImageObject` dict, not an array (unlike
  `rt-scraper`, which gets a list) — the extractor normalizes both shapes
  into a flat `images` list.
- `articleSection` was empty string on every sample.
- `datePublished`/`dateModified` use a `YYYY-MM-DD HH:MM:SS+00:00` space-
  separated format (not `T`-separated ISO 8601) — kept as-is, raw
  passthrough (not reformatted).

Full text comes from `div.article__body-text > p` (plain `<p>` tags, no
ad/embed noise found in the container across 4 samples — one sample had
an embedded YouTube iframe wrapped in `div.frame-block`, which
`find_all("p")` skips automatically since it targets `<p>` tags only).

Byline comes from `a.article__author-name` (plain text, e.g. `"Nariman
Mergalym"`). A sibling `div.article__author-position` was also found and
is captured as `authorPosition` — **on all 4 samples this held
untranslated Russian text** (`"Автор"`, i.e. "Author"), a real content
quirk of the English edition, kept as raw passthrough rather than
translated or dropped.

### 2. Latest headlines — `S2-feed`

`GET https://qazinform.com/feed.xml`

Not a standard RSS/Atom feed — a ROR-format sitemap/feed hybrid (`xmlns:
ror="http://rorweb.com/0.1/"`) with 50 items, newest-first (verified:
top entry matches the freshest homepage story at fetch time). Standard
`<item><link>/<title>/<description>/<pubDate>` fields plus
`<media:thumbnail url="..."/>` and a `<content:encoded>` CDATA block that
carries the **full article HTML**, unusual for this portfolio (matches
the `rt-scraper` RSS pattern) — includes a `<header><h1>`, a
`div.info` block (Russian relative timestamp, e.g. `"Сегодня, 11:25"` —
"Today, 11:25" — plus the author name), a lead `<figure>`, the body
paragraphs, and a trailing `<ul class="tags">` of tag links.

**Malformed-HTML quirk:** unlike the live article page, this feed's body
**also includes the lede sentence** (which duplicates the item
`<description>`), wrapped in `<p><strong><p>...</p></strong></p>` —
invalid nested `<p>` inside `<strong>` inside `<p>`. lxml's parser
auto-repair turns this into **two adjacent, textually-identical `<p>`
tags** in the parsed tree. `_paragraphs_to_text()` in `extractor.py`
drops any paragraph whose text is identical to the one immediately
before it, which removes exactly this duplication without dropping any
real content (verified: the lede sentence appears exactly once in
`latest`-mode output, see README sample).

The feed's embedded `div.author` is used directly for the `author` field
in `latest` mode, so a follow-up `article`-mode fetch isn't required to
get the byline.

`<ror:*>` elements (`updatePeriod`, `sortOrder`, `resourceOf`) carry no
useful per-article data and are ignored.

## Paywall behavior

None observed. State news agency, fully open-access — no
"subscribe"/paywall markers found on any of the 4 sampled articles.

## Known limits

- 404s for non-existent article slugs are **real HTTP 404s** (confirmed
  on a deliberately-invented slug) — no soft-404 quirk observed.
- Only 4 articles sampled in depth (general news, business/oil, politics
  x2), all sharing the exact same template. A structurally different
  article type (opinion/op-ed with a byline different from the standard
  `article__author-name` pattern, live-blog, photo gallery) was not
  sampled.
- `datePublished`/`dateModified` are always identical on every sample
  seen — a genuinely edited/updated article (where they'd differ) was
  not observed.
- `/feed.xml` returns a fixed 50 items with no observed pagination
  parameter; `limit` in `latest` mode is capped at 50 to match.

## Diff cadence

Quarterly smoke test recommended.
