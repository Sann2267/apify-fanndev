# Crawling Method — Malay Mail

**Last verified:** 2026-08-26

## robots.txt

Independently re-fetched (not just relying on the orchestrator's fast
screen). `malaymail.com/robots.txt` returns 200 and has **no
Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai-specific stanza
at all**, and **no blanket `Disallow: /`**. The only groups are a generic
`User-agent: *` and a `User-agent: grapeshot` (empty disallow):

```
User-agent: *
Disallow: /ajax/*
Disallow: /print*
Disallow: /getRelatedArticles*
Disallow: /getMostReadArticles*
Disallow: /article_count/*
Disallow: /get-menu-header*
Disallow: /search*
Disallow: /morearticles/*
Disallow: /article.php*
Disallow: /login-mgt
Disallow: /*.php
Disallow: /archive/*
Disallow: /widget/*
Disallow: */page/*
Disallow: /test/
Disallow: /test*

User-agent: grapeshot
Disallow:

Sitemap: https://www.malaymail.com/sitemap.xml
```

None of the disallowed paths (`/ajax/`, `/print`, `/search`, `/archive/`,
`/widget/`, paginated `/page/` listings, `.php` endpoints) are touched by
this actor -- it only fetches article URLs (`/news/<section>/<date>/<slug>/<id>`)
and the RSS feed (`/feed/rss`). Clear to build.

## WAF

`malaymail.com` is fronted by **Cloudflare + CloudFront**
(`server: cloudflare`, `x-amz-cf-id`/`via: ... CloudFront` headers, `cf-ray`
present) but shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on the homepage, article pages, and the RSS feed -- no
`cf-mitigated` header, no "Just a moment" interstitial, no 403. A
Cloudflare email-obfuscation script (`/cdn-cgi/scripts/.../email-decode.min.js`)
is present on article pages but is passive (not an active challenge).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.malaymail.com/news/<section>/<yyyy>/<mm>/<dd>/<slug>/<id>`

Every sampled article page (hard news, wire/Bernama copy, and an opinion
column) carries a `NewsArticle` ld+json block:

```html
<script data-cfasync="false" type="application/ld+json">
```

**Quirk:** the `type="application/ld+json"` attribute is NOT first in the
tag (`data-cfasync="false"` comes before it) -- a regex that assumes
`<script type="application/ld+json">` literally will miss it. The extractor
regex matches `<script[^>]*type="application/ld\+json"[^>]*>` instead.

Fields present: `keywords`, `headline`, `description`, `articleSection`,
`@context`, `@type` (`"NewsArticle"`), `inLanguage`, `mainEntityOfPage`
(`{"@type":"WebPage","@id": <canonical URL>}`), `image`
(`{"@type":"ImageObject","url","width","height"}`), `datePublished`,
`dateModified` (both ISO 8601 with `+08:00` offset), `speakable`
(`cssSelector: [".article-title", ".article-body"]`), `author`
(`{"@type":"Person","name"}` -- verified this reflects the **real byline**,
e.g. `"Erna Mahyuni"` on an opinion column, not a generic `"Malay Mail"`
placeholder used on wire copy), `publisher` (Organization with
name/alternateName/sameAs social links/logo).

**No `articleBody` in the ld+json block** -- the full text lives in the page
HTML itself, in `<div class="article-body">` (confirmed by the `speakable`
selector hint), as a sequence of `<p>` tags interleaved with ad/embed
placeholder `<div>`s: `#mm-story-outstream`, `#mm-story-mreg-2`,
`#mm-story-mreg-4`, `#mm-teads`, `.vodus-banner`, `.sidebar-square-ad`. The
extractor selects `div.article-body`, strips those placeholder elements
(plus any stray `<script>`), and keeps the remaining inner HTML verbatim as
`content`, with a flattened plain-text `articleBody` convenience field
built by joining `<p>` text.

**404 handling:** a nonexistent slug returns a real **HTTP 404** status
code (verified against a deliberately-invented slug/id) with a normal
`ERROR 404` HTML page (no ld+json block on it). The actor checks
`response.status_code == 404` *before* attempting to parse ld+json, so
this never reaches the parser as a shape-mismatch crash.

### 2. Latest headlines — `S2-rss`

`GET https://www.malaymail.com/feed/rss`

Discovered via the site's own `/rss` landing page (`<title>RSS Feeds |
Malay Mail</title>`), which links section feeds (`/feed/rss/malaysia`,
`/feed/rss/world`, etc.) plus one site-wide `/feed/rss`. Standard RSS 2.0,
**50 items per fetch**. Per item: `title`, `link`, `guid`
(`isPermaLink` not set but value matches `link`), `description` (plain-text
teaser, HTML-entity encoded), **`<content:encoded>` carrying the FULL
article HTML** (verified: identical paragraph text to the article page's
`article-body` div, plus an embedded `<div class="image_body">` inline
image block not present on the article page's stripped-down JSON-LD),
`dc:creator` (byline -- **can be empty/absent**, e.g. Bernama wire copy has
no `<dc:creator>` element at all, unlike the opinion column which had
`Erna Mahyuni`), `pubDate`, `media:thumbnail` (`url` attribute, lead
image), and **a single `<dc:subject>` element** holding a comma-separated
keyword string (e.g. `"Chiikawa  ,University of Hiroshima  ,Kawaii..."`) --
**not** repeated `<category>` tags like most of the portfolio. The
extractor splits this on commas into a `categories` list for consistency
with other actors' latest-mode shape.

Because `content:encoded` already carries the complete article, the same
`_flatten_html()` helper used for article mode is reused here too, so
`latest` mode records also get a full plain-text `articleBody` field for
free.

No Google News sitemap was used for the "latest" mode even though
`sitemap.xml` is itself a live Google-News-formatted feed (confirmed while
recon'ing -- it carries `news:title`/`news:publication_date`/`news:keywords`
per `<url>`) since the RSS feed already fully covers the "newest
headlines" use case with more data per item (full article HTML) than the
sitemap carries (headline + keywords only).

## Paywall behavior

None observed. Malay Mail is a free, ad-supported, digital-first Malaysian
tabloid-style outlet -- no `isAccessibleForFree`/paywall field in the
ld+json block, no subscribe/paywall overlay found in sampled HTML
(`paywall`/`premium-content`/`metered`/`piano.io` all absent from the raw
HTML of a sampled article).

## Known limits

- 3 articles sampled in depth (2 hard-news/wire, 1 opinion column). All
  three used the identical ld+json shape and `div.article-body` structure.
  A structurally different template (photo gallery, video feature,
  live-blog, sponsored "mediaoutreach" content seen in the sitemap) was
  not sampled and might carry a different body-HTML shape.
- `author`/`publisher`/`image`/`mainEntityOfPage`/`speakable` are kept as
  their raw nested ld+json object shape rather than flattened, per the
  raw-passthrough convention.
- RSS `dc:creator` is frequently empty/absent on wire-service copy (only
  bylined opinion/analysis pieces reliably carry it) -- `creator` is `null`
  on those records rather than a placeholder string.

## Diff cadence

Quarterly smoke test recommended.
