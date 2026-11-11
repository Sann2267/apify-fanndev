# Crawling Method — 24.kg

**Last verified:** 2026-08-27

24.kg is Kyrgyzstan's leading news agency, published at `24.kg`. This is
the **first Kyrgyzstan outlet in this portfolio** (Central Asia had only
`kazinform-scraper`, Kazakhstan, before this). The site is bilingual
**Russian/Kyrgyz** — no separate English edition was found or attempted;
content is passed through in whichever language it was published, not
translated (consistent with this portfolio's existing Russian-only outlets
such as `tass-scraper`, `rt-scraper`, `meduza-scraper`).

## Robots.txt

```
User-Agent: *
Allow:/
Disallow: */print$
Disallow: */print/$
Disallow: /poisk_po_sajtu/*
sitemap: https://24.kg/sitemap.xml
Host: https://24.kg
```

Six lines total. One `User-Agent: *` group with an explicit `Allow:/`, and
only three narrow `Disallow` paths (a print-view URL suffix and the
internal site-search endpoint) — nothing that touches article pages or the
RSS feed used by this actor. No `Claude`/`ClaudeBot`/`Claude-Web`/
`Claude-User`/`Claude-SearchBot`/`anthropic-ai` user-agent group anywhere,
and no plain-English natural-language prohibition against AI/LLM
training/scraping in the file (it's six lines, nothing but directives —
no comments at all). Independently re-verified with a fresh `curl`
fetch during this build (`GET https://24.kg/robots.txt` -> HTTP 200, body
as above) — confirmed crawlable.

## WAF

None found. `curl_cffi` `chrome124` gets a clean HTTP 200 on the homepage
(`server: nginx/1.31.2`), and — unusually for this portfolio — a **plain,
non-impersonated `requests.get()` gets an identical clean 200** on the same
URL. No Cloudflare/PerimeterX/DataDome/Akamai markers observed anywhere
during recon (homepage, RSS feed, sitemap index, 6 sampled article pages
across 4 categories, 2 deliberately-invalid URLs). `chrome124` is pinned
anyway, consistent with the portfolio-wide default, since a plain
`requests` baseline is fragile long-term (UA/TLS-based blocking can be
added at any time without notice).

## Data sources

### 1. Article pages — `S1-meta+html`

`GET https://24.kg/<section>/<numeric-id>_<slug>/`

**No JSON-LD `NewsArticle` block.** The only
`<script type="application/ld+json">` on an article page is a
`BreadcrumbList` (2 entries: section, then the article itself). This is a
genuine gap from this portfolio's usual JSON-LD-first pattern.

Instead, the article is marked up with **schema.org microdata** —
`<div itemscope itemtype="http://schema.org/NewsArticle">` wrapping the
byline/date/image block, with `itemprop="..."` attributes inline in the
HTML (not a separate script block). This is one layer down the extraction
stability ladder from JSON-LD (still structured metadata, not raw CSS
scraping) and is used to positively confirm a page is an article.

**Microdata date quirk:** the microdata's own `dateModified`/
`datePublished` attribute values carry a genuine site bug — a stray
literal backslash character immediately before the closing quote, e.g.:

```html
<meta itemprop="dateModified" content="2026-08-26\"/>
<span itemprop='datePublished' content='2026-08-26\'>22:51, 26 августа 2026</span>
```

That backslash is a literal character in the parsed attribute value (not
an escape — HTML has no backslash-escaping), and the `datePublished`
attribute only carries a bare date, not a timestamp (the human-readable
text alongside it, "22:51, 26 августа 2026", carries the time but isn't
machine-parseable without locale-aware Russian month-name parsing).

**Dates are pulled from the OpenGraph/`article:*` meta tags instead**,
which are clean, complete, and bug-free:

```html
<meta property="article:published_time" content="2026-08-26T22:51:00+06:00">
<meta property="article:modified_time" content="2026-08-26T22:43:48+06:00">
```

`headline` comes from `<meta itemprop="headline" content="...">` (falls
back to `h1.newsTitle` text if that meta tag is ever missing — not
observed missing on any of the 6 samples). `description` comes from
`<meta name="description">`. `section` comes from
`<meta property="article:section">`. `image` from
`<meta property="og:image">`. `keywords` from `<meta name="keywords">`,
kept as the raw comma-separated string (not split into a list — raw
passthrough).

`author` comes from `<meta name="author" content="...">` — **present on
Russian-language byline articles, but genuinely absent (no tag emitted at
all, not an empty one) on some articles**, observed on a Kyrgyz-language
(`/kyrgyzcha/`) sample. Treated as optional (`None`), not a shape error.

Full body text comes from `div.cont[itemprop="articleBody"]`, direct
`<p dir="ltr">` child paragraphs, joined with `\n\n`.

**Bilingual quirk:** `<html lang="...">` reliably reflects the actual
article language — `ru-RU` on Russian-section articles (`/obschestvo/`,
`/ekonomika/`, `/sport/`, `/proisshestvija/`, ...), `ky-KG` on
`/kyrgyzcha/` articles. The `og:locale` meta tag is **hardcoded `ru_ru`
site-wide**, including on confirmed Kyrgyz-language pages — a site bug, not
used. `_lang` in the output is read from `<html lang>`.

**HTML-entity quirk (article HTML only):** none observed — the lxml HTML
parser decodes `&nbsp;`/`&laquo;`/`&raquo;` etc. correctly on article
pages, unlike the RSS feed (see below). `html.unescape()` is still applied
uniformly in `_clean_text()` for defense-in-depth; it's a no-op here.

**Non-article pages** (e.g. a category listing like `https://24.kg/ekonomika/`)
carry neither the `NewsArticle` itemtype nor the `articleBody` div —
detected explicitly and reported as `_error: "not_article"` rather than
raising.

**Slug-is-decorative quirk:** the numeric ID prefix in the URL path is
what the server actually keys on — a URL with a valid numeric ID but a
completely wrong/garbage slug (`/proisshestvija/386730_invalidslugtest12345/`)
still serves the real article with HTTP 200 (confirmed live). Only a
nonexistent numeric ID (`/proisshestvija/999999999_totally_fake_.../`)
produces a real HTTP 404. Not treated as a bug in the extractor — any 200
response is extracted normally regardless of slug text, matching the
site's own routing behavior.

### 2. Latest headlines — `S2-rss`

`GET https://24.kg/rss/`

A plain RSS 2.0 feed, ~50 `<item>` entries observed in one fetch,
newest-first (`lastBuildDate` matched fetch time, `ttl` 10 minutes).
Each item carries `title`, `link`, `description` (teaser), `category`,
`pubDate` (RFC 822), and `guid` (identical to `link` on this site) — no
embedded full article body (unlike Kazinform's `feed.xml`, which embeds
full HTML in `content:encoded`), so `latest` mode returns teaser-only
records here.

**Double-encoded HTML-entity quirk (RSS only, genuine site bug):** feed
titles/descriptions are wrapped in `<![CDATA[...]]>` blocks that
themselves contain literal HTML-entity syntax, e.g.:

```xml
<title><![CDATA[В&nbsp;городе&nbsp;Ош задержали иностранца, пытавшегося дать взятку милиционеру
]]></title>
```

Per the XML spec, entities are **not** expanded inside CDATA sections, so
BeautifulSoup's XML parser correctly returns the literal text
`В&nbsp;городе&nbsp;Ош...` rather than a decoded non-breaking space. This
is the site's own double-encoding bug (they HTML-escaped the text before
wrapping it in CDATA, which doesn't need escaping). `html.unescape()` is
applied to every RSS-derived text field in `_clean_text()` to undo this —
confirmed it cleanly turns `В&nbsp;городе&nbsp;Ош` into `В городе Ош` (and
similarly resolves `&laquo;`/`&raquo;` guillemets) with no double-unescape
risk, since running `html.unescape()` on already-clean HTML-mode text is a
harmless no-op.

`sitemap.xml` was also checked as a potential `latest`-mode alternative:
it's a **sitemap index of archive-only sitemaps** (`sitemap_english_0.xml`,
`sitemap_russian_0.xml`...`_3.xml`, plus several `before_2022/` files),
all with `lastmod` dates around 2022-06-04 — clearly a historical/archive
index, not a live feed. `/rss/` is the correct and only live `latest`
source.

## Paywall behavior

None observed. No `subscribe`/`premium`/`paywall` string hits found on any
sampled article page — 24.kg is a free, open-access, ad-supported site.

## Known limits

- No English edition exists or was found; content is Russian or Kyrgyz
  depending on section, passed through as-is (see `_lang`).
- 6 articles sampled in depth across 4 sections (`/proisshestvija/`,
  `/obschestvo/`, `/ekonomika/`, `/sport/`, `/kyrgyzcha/`) plus one
  category-listing page and two deliberately-invalid URLs. A structurally
  different template (live-blog, video feature, photo-gallery, opinion
  column) was not sampled.
- `author` is legitimately absent on some articles (not every piece has a
  byline) — `None` in that case, not an error.
- The RSS feed caps at ~50 items per fetch; `limit` above that is not
  achievable from this source without pagination, which the feed does not
  offer.

## Diff cadence

Quarterly smoke test recommended.
