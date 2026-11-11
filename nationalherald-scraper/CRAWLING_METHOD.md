# Crawling Method — National Herald

**Last verified:** 2026-08-27

National Herald (`nationalheraldindia.com`) is an Indian English-language
daily/news portal headquartered in New Delhi, originally founded by
Jawaharlal Nehru in 1938.

## robots.txt

`https://www.nationalheraldindia.com/robots.txt` returns 200 with:

```
User-agent: *
Disallow:

Sitemap: https://www.nationalheraldindia.com/news_sitemap.xml
Sitemap: https://www.nationalheraldindia.com/sitemap.xml
Sitemap: https://www.nationalheraldindia.com/sitemap/sitemap-section.xml
Sitemap: https://www.nationalheraldindia.com/sitemap/sitemap-topic.xml
Sitemap: https://www.nationalheraldindia.com/sitemap/sitemap-static-pages.xml

User-agent: Mediapartners-Google
Allow: /
User-agent: Googlebot-News
Allow: /
```

An unqualified `Disallow:` (empty value) under `User-agent: *` means
allow-all — no path is blocked for any crawler. No explicit
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
disallow anywhere, no blanket `Disallow: /`, and no plain-English
natural-language prohibition against AI/LLM training or scraping anywhere in
the file (it carries no comments at all). Independently re-verified twice
during this build — once with a plain `curl_cffi` `chrome124` fetch and once
again from a second script run — both returned the identical body above
(HTTP 200). Clear to build.

## WAF

`nationalheraldindia.com` is fronted by **Cloudflare** (`server: cloudflare`)
but presented **no challenge** to plain `curl_cffi` `chrome124`
impersonation during recon: homepage, `robots.txt`, 3 article pages spanning
different sections (Politics, National, International), `news_sitemap.xml`,
and the `stories.rss` feed all returned clean 200s with full content — no
"Just a moment"/`challenge-platform`/captcha body markers, no unexpected
403/429/503.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.nationalheraldindia.com/<section>/<slug>`

Each article page emits 7 separate `application/ld+json` blocks (`WebPage`,
`ImageObject`, `Organization`, `WebSite`, `BreadcrumbList`, `NewsArticle`,
and one array-shaped block of `SiteNavigationElement` entries) —
`extract_article` picks out the `NewsArticle` one specifically. This site
runs the **Quintype/AssetType CMS** (`cf-images.assettype.com` image CDN
host, `/stories.rss` feed shape) — the same CMS as `newindianexpress-
scraper` and `freepressjournal-scraper` elsewhere in this portfolio.

The `NewsArticle` node carries `headline`/`name` (duplicated), `description`,
`keywords` (comma-separated, often populated), `articleSection` (single
upper-case string, e.g. `"POLITICS"`), `author` (list of `Person` objects
with `givenName`/`name`/`url`), `image` (a **single** `ImageObject` dict —
**not a list**, unlike newindianexpress-scraper's shape), `thumbnailUrl`
(same URL as `image.url` on every sample), `mainEntityOfPage`, `isPartOf`
(with a nested `primaryImageOfPage`), and `datePublished`/`dateModified`/
`dateCreated` (ISO 8601 with `+05:30` offset). `articleBody` carries the
**full article text as HTML** — see the escaping quirk below. Confirmed
consistent shape across 3 samples (Politics, National, International).

**Quirk — double-HTML-escaped `articleBody`:** the `articleBody` string is
itself HTML markup (`<p>...</p>` paragraphs, including an inline
`<em>`-tagged Telegram-channel promo block at the end of some articles), but
that markup has been HTML-entity-escaped a *second* time inside the JSON
string — the literal characters are `&lt;p&gt;Some text&lt;/p&gt;`, not
`<p>Some text</p>`. Confirmed on all 3 sampled articles. This is a distinct
quirk from the single-level WordPress `&amp;`-in-plain-text escaping seen on
Punch/Guardian Nigeria elsewhere in this portfolio — here it's markup being
escaped, not punctuation. Per this portfolio's raw-passthrough convention
(output upstream's field shape verbatim, let downstream normalize),
`articleBody` is passed through **exactly as upstream serves it**, still
entity-escaped — no `html.unescape()` is applied. A downstream consumer
that wants clean HTML or plain text should call `html.unescape()` (and
optionally strip tags) themselves. No other JSON-LD field on the
`NewsArticle` node (`headline`, `name`, `description`, `keywords`,
`articleSection`) showed this escaping on any sample.

**Quirk — near-empty `publisher` stub:** every sampled article's
`NewsArticle.publisher` is `{"@type": "Organization", "@context":
"http://schema.org", "id": ""}` — no real publisher name or logo. (A
separate, fully-populated top-level `Organization` ld+json block *does*
exist on the page with `name: "National Herald"` and a real logo/address,
but per raw-passthrough convention this actor does not cross-reference or
repair the `NewsArticle.publisher` stub from a different ld+json block —
it's passed through as-is, and the quirk is documented here so downstream
consumers know not to rely on it for the publisher name.)

**No `isAccessibleForFree`/paywall-signal field** was observed on any
sampled article's JSON-LD (unlike freepressjournal-scraper, which carries
`isAccessibleForFree: true`) — see Paywall section below.

**404 handling:** a genuinely nonexistent/invented article slug returns a
**real HTTP 404** with a "Page not found - National Herald" HTML page —
confirmed on a deliberately-invented slug. No soft-404 quirk observed
(unlike freepressjournal.in's `Refresh:`-header pattern).

### 2. Latest headlines — `S2-rss`

`GET https://www.nationalheraldindia.com/stories.rss`

(`/feed` serves byte-for-byte identical content — `/stories.rss` used for
naming consistency with the other Quintype/AssetType actors in this
portfolio.) Same rich shape as newindianexpress-scraper's and
freepressjournal-scraper's identically-named feed: standard
`title`/`link`/`guid`/`pubDate`/`description` (description **is**
populated here, unlike NIE's feed where it's usually blank) plus
`atom:author`/`atom:name`/`atom:uri` (byline + `/api/author/<id>` profile
path), `media:keywords` (comma-separated, sometimes empty), `category`
(1-3 values per item, e.g. `POLITICS`, `Nation`, `Education`),
`media:content`/`media:thumbnail` (lead image URLs), and `content:encoded`
(the **full article body as clean HTML**, i.e. NOT double-escaped like
article-mode's `articleBody` — this feed's HTML comes through as real
`<p>` tags). Confirmed live with 3+ items across multiple sections in one
fetch on 2026-08-27.

**Parser note:** BeautifulSoup's `xml` (lxml-xml) parser strips namespace
prefixes from tag names, so `item.find("author")` matches `<atom:author>`,
`item.find("name")` matches `<atom:name>`, `item.find("keywords")` matches
`<media:keywords>`, `item.find("content")` matches `<media:content>`,
`item.find("thumbnail")` matches `<media:thumbnail>`, and
`item.find("encoded")` matches `<content:encoded>`. Verified against a live
downloaded copy of the feed before wiring `extract_rss_items`.

`news_sitemap.xml` was also confirmed to return a clean 200 with real,
freshly-dated entries (a viable `S3-sitemap` fallback if the RSS feed is
ever retired), but `stories.rss` was chosen as the primary latest-mode
source since it already carries a full HTML body per item in one
lightweight request, consistent with the sibling Quintype-CMS actors in this
portfolio.

## Paywall behavior

No paywall/metering markers found: no `isAccessibleForFree` field on any
sampled article's JSON-LD, and a full-text search of a sampled article page
for `paywall`/`Paywall`/`subscribe to continue`/`metered`/`premium-content`
returned zero hits. `articleBody` length ranged 3,300-6,300 characters
across the 3 samples with no visible truncation. National Herald's main
news content appears to be free, open-access. Only News/Politics/
International sections were sampled in depth — Opinion/Editorial content
(a category some Indian outlets meter) was not specifically probed.

## Known limits

- Only 3 articles sampled in depth (Politics, National, International).
  Opinion/Editorial, a live-blog, or a video-feature template was not
  sampled and may have a different JSON-LD shape or a paywall not present
  on breaking-news content.
- `latest` mode returns whatever `stories.rss` currently carries — no
  section-specific feed variants were probed since the site-wide feed
  already spans many sections.
- `image`/`thumbnail` field shape differs between modes: article-mode
  `image` is a single `ImageObject` dict; latest-mode `image` is a single
  URL string (from `media:content`). Raw passthrough of each source's
  native shape, not normalized.
- `articleBody` (article-mode) is double-HTML-escaped upstream and passed
  through unescaped by this actor (see Quirk above) — `contentEncoded`
  (latest-mode) is NOT affected and carries clean HTML.
- `publisher` (article-mode) is a near-empty stub with no real name/logo
  (see Quirk above).

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If National Herald redesigns the page, `extract_article`
will raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
