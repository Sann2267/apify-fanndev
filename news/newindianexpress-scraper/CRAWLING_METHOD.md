# Crawling Method — The New Indian Express

**Last verified:** 2026-08-26

## robots.txt

`https://www.newindianexpress.com/robots.txt` returns 200 with:

```
User-agent: *
Sitemap: https://www.newindianexpress.com/sitemap.xml
Sitemap: https://www.newindianexpress.com/news_sitemap.xml
Allow: /
```

No explicit Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai
disallow, no blanket `Disallow: /`. Independently re-verified with a fresh
`curl` (not reused from any prior fast screen) before any code was written,
per this portfolio's policy after the "Babak 14" incident. Clear to build.

Note: this outlet (`newindianexpress.com`, published by Express Publications
Madras) is a **separate publisher** from Indian Express (`indianexpress.com`,
which explicitly blocks Claude/anthropic-ai per this project's research doc)
-- do not confuse the two when reading the market-research log.

## WAF

`newindianexpress.com` is fronted by **Cloudflare** (`server: cloudflare`,
`cf-ray` present, `cf-cache-status` on every response) but presented **no
challenge** to plain `curl_cffi` `chrome124` impersonation during recon:
homepage, 5 article pages spanning different sections (Karnataka, Bengaluru,
Odisha, Chennai, Tamil Nadu, Entertainment), the news sitemap, and the
`stories.rss` feed all returned clean 200s with full content -- no "Just a
moment"/`challenge-platform`/captcha body markers, no unexpected 403/429/503.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.newindianexpress.com/<section>/<subsection>/<yyyy>/<Mon>/<dd>/<slug>`

Each article page emits 5 separate `application/ld+json` blocks
(`BreadcrumbList`, `WebPage`, `SiteNavigationElement`, `Person`,
`NewsArticle`) -- `extract_article` picks out the `NewsArticle` one
specifically. It carries `articleBody` with the **full plain-text article**
(1,300-10,400 characters across 5 samples spanning news, sports, and
long-form entertainment obituary content), `headline`/`name` (duplicated),
`description`, `keywords` (comma-separated string, often empty),
`articleSection`, `author` (array of `Person` objects with `givenName`/
`name`/`url` -- named reporters, not desk credits, on every sample),
`image` (array of 3 `ImageObject` crops per article), `thumbnailUrl`,
`publisher` (`NewsMediaOrganization` with logo + `sameAs` social links),
and `datePublished`/`dateModified`/`dateCreated`.

No `isAccessibleForFree`/`hasPart` or any other schema.org paywall-signal
field was observed on any sampled article -- New Indian Express's main news
content does not appear to carry a metering/paywall marker.

No `__NEXT_DATA__` was found -- this site does not expose page state via
Next.js SSR data injection (CMS appears to be Quintype/AssetType, based on
the `cf-images.assettype.com` image CDN host).

**Encoding check:** the JSON-LD `headline` field on one sample contained the
byte sequence `\xe2\x80\x99` (correct UTF-8 for U+2019, a right single
quotation mark, e.g. "Karnataka's"). This is valid UTF-8 -- it only renders
as `<0xEF><0xBF><0xBD>` (replacement character) in a non-UTF-8 terminal.
Confirmed via direct byte-level decode that no `html.unescape()` fix or
mojibake repair is needed for this outlet, unlike several other India actors
in this portfolio.

**404 handling:** a nonexistent slug 301-redirects to a lowercased URL
variant (`.../2026/Aug/26/...` → `.../2026/aug/26/...`), which then serves a
genuine 404. `curl_cffi`'s `AsyncSession` follows redirects by default, so
`client.get()` transparently lands on the final 404 status -- no special
redirect handling was needed in `main.py`, same pattern as the rest of the
portfolio.

### 2. Latest headlines — `S2-rss`

`GET https://www.newindianexpress.com/stories.rss`

(`/feed` 302-redirects here; this is the confirmed default site-wide feed,
not a single-section feed.) Richer than a typical RSS 2.0 feed: standard
`title`/`link`/`guid`/`pubDate`/`description` (description is usually empty
on this feed) plus `atom:author`/`atom:name`/`atom:uri` (byline + profile
path), `media:keywords` (comma-separated), `category` (single value per
item, one of many sections -- states, cities, entertainment, sports, etc.,
not limited to one), `media:content`/`media:thumbnail` (lead image URLs),
and `content:encoded` (the **full article body as HTML markup**, i.e. this
feed carries full text, not just headlines). Confirmed live with 22 items
across ~7 distinct categories in one fetch on 2026-08-26.

**Parser note:** BeautifulSoup's `xml` (lxml-xml) parser strips namespace
prefixes from tag names, so `item.find("author")` matches `<atom:author>`,
`item.find("name")` matches `<atom:name>`, `item.find("keywords")` matches
`<media:keywords>`, `item.find("content")` matches `<media:content>`,
`item.find("thumbnail")` matches `<media:thumbnail>`, and
`item.find("encoded")` matches `<content:encoded>`. Verified against a live
downloaded copy of the feed before wiring `extract_rss_items`.

## Paywall behavior

No paywall markers or truncation observed on any sampled article (news,
sports, entertainment/obituary long-form).

## Known limits

- `latest` mode returns whatever `stories.rss` currently carries (~22 items
  at last check) -- no section-specific feed variants were probed since the
  site-wide feed already spans many categories.
- `keywords` is empty on most sampled article-mode JSON-LD (unlike the RSS
  feed's `media:keywords`, which is reliably populated) -- passed through
  as-is either way, not backfilled from one source to the other.
- `image`/`thumbnail` field shape differs between modes: article-mode
  `image` is a list of `ImageObject` dicts (multiple crops); latest-mode
  `image` is a single URL string (from `media:content`). This is raw
  passthrough of each source's native shape, not normalized.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If New Indian Express redesigns the page, `extract_article`
will raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
