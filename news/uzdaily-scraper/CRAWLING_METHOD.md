# Crawling Method — UzDaily (English edition)

**Last verified:** 2026-08-26

UzDaily is an Uzbekistan business/news portal. This is one of the first
Uzbekistan outlets added to this portfolio (alongside `gazetauz-scraper`).

## Domain scoping — multi-language site, English path prefix

The bare domain `uzdaily.uz` 301-redirects to `www.uzdaily.uz`. The site is
multi-language (`/ru/`, `/en/`, `/uz/`, `/uzc/` path prefixes on the same
domain, not separate hosts). This actor is scoped to the `/en/` prefix
(the English-language business/news edition, matching the outlet's stated
identity). Article URLs look like:

```
https://www.uzdaily.uz/en/central-asia-fintech-group-calls-for-unified-financial-rails/
```

## robots.txt / Claude screening

`https://uzdaily.uz/robots.txt` -> 301 -> `https://www.uzdaily.uz/robots.txt`
-> HTTP 200:

```
User-agent: Googlebot
Allow: /
...
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: Bytespider
Allow: /

User-agent: *
Disallow: /admin/
Disallow: /login/
Disallow: /private/

Sitemap: https://www.uzdaily.uz/sitemap.xml
Sitemap: https://www.uzdaily.uz/ru/googlenews_sitemap/
Sitemap: https://www.uzdaily.uz/en/googlenews_sitemap/
Sitemap: https://www.uzdaily.uz/uz/googlenews_sitemap/
Sitemap: https://www.uzdaily.uz/uzc/googlenews_sitemap/
```

`ClaudeBot` and `anthropic-ai` are **explicitly listed with `Allow: /`**,
alongside `GPTBot`, `PerplexityBot`, `Applebot-Extended`, `Amazonbot`,
`Bytespider`. The wildcard `User-agent: *` group only disallows
`/admin/`, `/login/`, `/private/` (none of which this actor touches) — no
blanket `Disallow: /`. No comments in the file, so no natural-language
AI/LLM-training prohibition either. Re-verified independently (not just
relying on the orchestrator's fast screen) before writing any code.

## WAF

**None found.** Served directly by nginx (`Server: nginx/1.28.1`) behind
what is likely an internal CDN/cache layer (`X-Cache-Status: HIT`,
`Cache-Control` headers) — no Cloudflare, no challenge markers. Confirmed:
- plain `curl` (no TLS impersonation) gets a clean 200 homepage/article/RSS
- `curl_cffi` `impersonate="chrome124"` gets identical 200s
- a deliberately-invented article slug returns a genuine HTTP 404 (not a
  soft-404 or challenge page)

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default and the same profile used for `kazinform-scraper` (also Central
Asia). Retry/warmup scaffolding kept per convention even though nothing
observed requires it.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.uzdaily.uz/en/<slug>/`

The page (Drupal-based CMS) emits two ld+json blocks: `NewsArticle` and
`BreadcrumbList` (ignored). Unlike `kazinform-scraper` and
`arabnews-scraper`, the `NewsArticle` block here is **self-sufficient** —
it carries `articleBody` as real plain text (not HTML, unlike Arab News)
and a full `author` object, so no HTML-scraping fallback is needed at all.
Confirmed consistent across 4 sampled articles (finance, economy x2,
Uzbekistan/politics):

```json
{
  "@type": "NewsArticle",
  "headline": "...",
  "description": "...",
  "articleBody": "Tashkent, Uzbekistan (UzDaily.uz) — ...",
  "wordCount": 625,
  "image": ["https://www.uzdaily.uz/media/filer_public/.../foo.webp"],
  "datePublished": "2026-08-26T16:23:00+05:00",
  "dateModified": "2026-08-26T19:18:59.302382+05:00",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "articleSection": "Finance",
  "keywords": "keyword one, keyword two, ...",
  "author": {"@type": "Person", "name": "Anvar Umarov", "url": "https://www.uzdaily.uz/en/author/anvar-umarov/"},
  "publisher": {"@type": "NewsMediaOrganization", "name": "UzDaily.uz", "logo": {...}}
}
```

Quirks observed:
- **`articleBody` paragraph separator is a literal `\r\n\r\n`** (not
  wrapped in HTML `<p>` tags, unlike `arabnews-scraper`). `_clean_article_body()`
  in `extractor.py` normalizes `\r\n` -> `\n`, splits on the blank-line
  paragraph boundary, and collapses any stray single-newline line-wraps
  (observed once, inside a trailing byline signature block — e.g.
  `"Anna Bodrova,\r\nAlpari Analyst"`) into a single space per paragraph.
- `image` is already a **flat array of URL strings** (not `ImageObject`
  dicts) — `_images()` still normalizes the dict/list/string variants
  defensively, but the plain-string-array shape is what's actually seen.
- `datePublished`/`dateModified` use full ISO 8601 with a `+05:00`
  timezone offset (Uzbekistan time), already RFC-3339-clean — no
  reformatting needed, unlike Kazinform's space-separated dates.
- `keywords` is a single comma-separated string, kept as raw passthrough
  (not split into an array).
- `isAccessibleForFree` was `true` on every sampled article — see Paywall
  section below.
- The em-dash / smart-quote / non-breaking-space characters that appear
  as `�`-looking mojibake when `repr()`'d in a Windows console are
  **correctly UTF-8-encoded on the wire** (verified at the byte level:
  `\xe2\x80\x94` = U+2014 em dash, `\xc2\xa0` = U+00A0 nbsp) — this was a
  terminal-rendering artifact during recon, not a real encoding bug;
  `test_local.py`'s UTF-8 stdout reconfigure prints them correctly.

### 2. Latest headlines — `S2-rss`

`GET https://www.uzdaily.uz/en/rss/` (redirects 302 to a canonical RSS
URL under the same path)

Standard RSS 2.0 feed, ~20 items, newest-first (verified: top entry
matches the freshest homepage story at fetch time). Each `<item>` carries
`title`, `link`, `description` (short teaser — **not** the full article
body, unlike Kazinform's `/feed.xml`), `guid` (numeric internal article
ID, `isPermaLink="false"`), `pubDate` (RFC 822), `category`, and an
`<enclosure url="..." type="image/jpeg">` lead-image tag. No
`content:encoded` full-body block is present, so `latest` mode records
carry only a teaser — fetch the article URL in `article` mode for full
text.

## Paywall behavior

None observed. `isAccessibleForFree: true` on every sampled article
(finance, economy, Uzbekistan/politics categories) — free, open-access
business/news portal, no subscribe/paywall markers found in the HTML
either.

## Known limits

- 404s for non-existent article slugs are **real HTTP 404s** (confirmed
  on a deliberately-invented slug) — no soft-404 quirk observed.
- Only 4 articles sampled in depth (finance, economy x2,
  Uzbekistan/politics), all sharing the exact same JSON-LD template. A
  structurally different content type (opinion/op-ed, sports, live
  coverage, a multi-author byline) was not sampled.
- `/en/rss/` returns roughly 20 items with no observed pagination
  parameter; `limit` in `latest` mode is capped at 50 in the input schema
  for consistency with the rest of the portfolio, but requests above ~20
  will simply return fewer records than requested (`extract_rss_items`
  slices, it does not pad).
- Only the `/en/` (English) edition is in scope. `/ru/`, `/uz/`, `/uzc/`
  editions exist on the same domain but are out of scope for this actor.

## Diff cadence

Quarterly smoke test recommended.
