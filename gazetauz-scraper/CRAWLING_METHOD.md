# Crawling Method — Gazeta.uz (English edition)

**Last verified:** 2026-08-26

Gazeta.uz is Uzbekistan's major independent news portal. This is the
**first Uzbekistan outlet** added to this portfolio (Central Asia region
opened previously with `kazinform-scraper` for Kazakhstan).

## robots.txt / Claude screening

`https://www.gazeta.uz/robots.txt` -> HTTP 200:

```
User-Agent: *
Disallow: /adm/*
Disallow: /ru/adm/*
Disallow: /uz/adm/*
Disallow: /oz/adm/*
Disallow: /en/adm/*
Disallow: /clk/
Disallow: /*/search
Disallow: /*/search/
Disallow: *facebook_link*
Disallow: *twitter_link*
Disallow: *instagram_link*
Disallow: *telegram_link*
Disallow: *?*
Allow: *?page=*
Allow: *?r=*
Allow: *?v=*
Allow: /*utm_*
Clean-param: utm_source&utm_medium&utm_campaign&utm_term&utm_type&utm_referrer&utm_content&utm_source_platform&fbclid

sitemap: https://www.gazeta.uz/sitemap.xml
```

Single `User-Agent: *` group. All `Disallow` lines are narrow functional
paths (admin panels per-locale, click-tracking redirects, on-site search,
social-share tracking links, generic query strings — with `page`/`r`/`v`
query params explicitly re-`Allow`ed). **No blanket `Disallow: /`.** No
`Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` token anywhere. **No comments in the file**, so no
natural-language AI/LLM-training prohibition either (the "Star Malaysia"
legal-notice-text pattern) — checked the raw response body directly, not
just parsed directives.

Conclusion: crawlable, no machine-readable or natural-language AI scraping
prohibition found. Article URL paths (`/en/YYYY/MM/DD/<slug>/`) and the
RSS feed (`/en/rss/`) used by this actor are not covered by any
`Disallow` rule.

## Language scoping — one domain, path-prefixed editions

Unlike `kazinform-scraper` (separate domain per language) or
`asharqalawsat-scraper` (separate subdomain), Gazeta.uz serves **4
language editions on a single domain** via path prefixes, confirmed via
`hreflang` alternates present on every page:

| Prefix | Language | hreflang |
| --- | --- | --- |
| `/ru/` | Russian | `ru` |
| `/uz/` | Uzbek (Cyrillic) | `uz-Cyrl` |
| `/oz/` | Uzbek (Latin) | `uz-Latn` |
| `/en/` | English | `en` |

This actor is scoped **entirely to the `/en/` prefix**. The English
edition is substantial, not a thin stub: dedicated section pages
(`/en/politics/`, `/en/economy/`, `/en/society/`, `/en/column/`), its own
RSS feed (`/en/rss/`), and its own Google News sitemap
(`/sitemap/google-news-en.xml`) — all updated same-day, in parallel with
the Russian edition (confirmed: the English `usd-sum` article published
2026-08-26T09:24:44+05:00, same-day as the Russian original at
`/ru/2026/08/25/usd-sum/`, which per the site's own `hreflang` alternate
list precedes it — Russian is clearly the source language, English a
same-day translation, not a stale afterthought).

## WAF

**None found.** Served directly by nginx (`Server: nginx/1.31.3`), with
`X-Powered-By: PHP/8.4.14` — a classic PHP+nginx stack, no CDN/WAF
fronting observed. Confirmed two ways on the same article URL and the RSS
feed, both returning clean 200s of matching byte size:
- plain `curl` (no TLS impersonation, generic UA)
- `curl_cffi` `impersonate="chrome124"`

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (retry/warmup scaffolding kept per convention even though nothing
observed requires it).

## Data sources

### 1. Article pages — `S1-microdata+html`

`GET https://www.gazeta.uz/en/YYYY/MM/DD/<slug>/`

**No `<script type="application/ld+json">` block exists anywhere on the
page** (confirmed absent on 6 sampled articles across the "news"
(`articleContent type-news`) and "column"/op-ed
(`articleContent type-articles`) templates). All structured data is
embedded as schema.org **microdata** directly on visible HTML tags
(`itemscope`/`itemprop` attributes), not a separate JSON blob:

```html
<div class="articlePage" itemscope itemtype="https://schema.org/NewsArticle">
  <meta itemprop="datePublished" content="2026-08-26T09:24:44+05:00" />
  <h1 id="article_title" itemprop="headline name">...</h1>
  <h4 itemprop="alternativeHeadline">...</h4>
  <div itemprop="articleBody" id="redactor">...</div>
  <span itemprop="author">Gazeta</span>
  <span itemtype="https://schema.org/BreadcrumbList">
    <span itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem">
      <a itemprop="item" href="/en/economy/"><span itemprop="name">Economy</span></a>
    </span>
  </span>
</div>
```

Quirks observed (consistent across all 6 samples):
- **`author` is always institutional** (`"Gazeta"` on news pieces,
  `"Gazeta.uz"` on op-eds/columns) — **never a personal byline, even on a
  guest-authored op-ed**. Confirmed on a piece explicitly bylined "Op-Ed
  by David Cameron" in the headline itself: `itemprop=author` still reads
  `"Gazeta.uz"`, not `"David Cameron"`. Kept as raw passthrough, not
  corrected — the actual author's name (when a guest author) generally
  only appears in the headline/body text, not in structured metadata.
- `datePublished` is full ISO 8601 with the `+05:00` (Uzbekistan)
  timezone offset — kept as-is.
- No `dateModified` microdata field found anywhere (unlike `article:modified_time`
  in the `<meta>` tags, which duplicates `article:published_time` on every
  sample seen — not exposed as a separate output field since it never
  differed from `datePublished` in testing).
- Tags come from `span[itemprop=about]` inside `div.articleTags` —
  lowercase, e.g. `"central bank"`, `"mirkomil kholboev"`.

Full body text comes from `div#redactor[itemprop=articleBody]`, walking
`<p>` tags after removing two kinds of embedded non-content markup:

- **Inline ad widget nested inside a `<p>` tag.** One paragraph in the
  raw HTML is structured as
  `<p><span class="fr-img-caption">...</span><div class="inpage-ad">...<script>...</script>...</div></p>`
  — an (invalid) `<div>`+`<script>` nested inside a `<p>`, which lxml's
  HTML parser tolerates without repositioning it out of the paragraph.
  `_extract_body()` `.decompose()`s every `div.inpage-ad` and every
  `<script>` tag found inside the body container *before* walking `<p>`
  tags, removing the ad copy/JS cleanly while keeping the image-caption
  text that shares the same `<p>` (verified: the caption text — e.g.
  "Dynamics of the US dollar exchange rate against the soum..." — comes
  through as its own paragraph in `articleBody`, with no ad copy or
  `<script>` text mixed in).
- A trailing empty `<div id="extra"></div>` (always empty in testing,
  decomposed defensively).

Minor cosmetic quirk: `get_text(" ", strip=True)` inserts a literal space
at every tag boundary, so a paragraph ending in an inline `<a>` link
directly followed by a period renders as `"...the past month ."` (space
before the period) rather than `"...the past month."` — a byproduct of
BeautifulSoup's separator-based text extraction around inline `<a>` tags,
not a data-fidelity issue. Not corrected, consistent with this
portfolio's general use of `get_text(" ", strip=True)` elsewhere.

### 2. Unsupported template — "Stories" longform (`/en/list/reporting/`)

A subset of longform pieces under the "Stories" section use a **completely
different template**, built on the Tilda page-builder (`t-rec`/`t004`/
`t107`/`t152`/`t257`-style drag-and-drop blocks), confirmed on a sampled
census-reporting story
(`https://www.gazeta.uz/en/2026/02/26/census/`). This page has **none**
of `h1#article_title`, `div#redactor`, or `itemprop=articleBody` anywhere.
`extract_article()` raises `UnexpectedShape` for these URLs (fail loud,
verified locally — see Known limits). Standard "news" and "column"/op-ed
templates (the vast majority of content, including everything reachable
from `/en/politics/`, `/en/economy/`, `/en/society/`, `/en/column/`) are
unaffected.

### 3. Latest headlines — `S2-rss`

`GET https://www.gazeta.uz/en/rss/`

Standard RSS 2.0 (English edition only), newest-first, 20 items on every
fetch (no pagination param found). Fields: `<title>`, `<link>`,
`<description>` (CDATA teaser — **not** the full article body, unlike
`kazinform-scraper`'s `feed.xml`), `<pubDate>` (RFC 822), `<enclosure
url="..."/>` (lead image), `<dc:creator>` (always `"Gazeta"`, same
institutional-byline pattern as the article page's `itemprop=author`).

**Quirk:** the `<description>` CDATA embeds **literal HTML entities**
(`&nbsp;`, `&mdash;`, `&rsquo;`) as plain text characters — CDATA sections
are not entity-decoded per the XML spec, so `BeautifulSoup`'s XML parser
hands them back unresolved (e.g. `"...yet to&nbsp;directly affect..."`).
`_clean_text()` runs `html.unescape()` on every field it touches (both
modes) to resolve these into real characters (non-breaking space,
em-dash, right single quote) rather than leaking raw entity codes into
the dataset.

There is also a Google News sitemap
(`/sitemap/google-news-en.xml`, 6 items only, no teaser text) — not used;
the RSS feed carries more items and a usable description/image/author per
item.

## Paywall behavior

None observed. Fully open-access, no "subscribe"/paywall markers found on
any sampled article. Footer states "Materials from this website may not be
reproduced or distributed without prior written permission" (standard
copyright notice, not a paywall/access restriction) and an "Online media
license No. 209073" line.

## Known limits

- 404s for non-existent article slugs are **real HTTP 404s** (confirmed
  on a deliberately-invented slug) — no soft-404 quirk observed.
- The "Stories" longform Tilda-template section (see above) is **not
  supported** — `extract_article()` raises `UnexpectedShape` for these
  URLs rather than returning a partial/empty record.
- `author` is always the institutional byline (`"Gazeta"`/`"Gazeta.uz"`),
  never the actual writer's name, even for clearly guest-authored op-eds
  — this is a genuine site metadata limitation, not an extractor bug.
- `/en/rss/` returns a fixed 20 items with no observed pagination
  parameter; `limit` in `latest` mode is capped at 50 (the feed itself
  will just return its 20 items if `limit` > 20).
- Only 6 articles sampled in depth (economy/business x2, politics x2,
  op-ed, general/scheduling news), all sharing the same 2 supported
  templates. A live-blog or photo-gallery template (if one exists outside
  "Stories") was not sampled.

## Diff cadence

Quarterly smoke test recommended.
