# Crawling Method — Oman Observer

**Last verified:** 2026-08-26

## robots.txt / Claude screening

`https://www.omanobserver.om/robots.txt` returns a single flat block:

```
User-agent: *
Disallow: /ajax/*
Disallow: /search*
Disallow: /article.php*
Disallow: /login-mgt
Disallow: /*.pdf
Disallow: /*.php
Disallow: /archive/*
Disallow: /widget/*
```

Only one `User-agent:` group exists in the entire file, so the documented
Babak-14 multi-group-parser trap (several `User-agent:` lines sharing one
`Disallow:` block below them) cannot apply here -- there's nothing to
mis-attribute. No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` token appears anywhere in the file
(case-insensitive check). None of the disallowed paths (`/ajax/`,
`/search`, `/article.php`, `/login-mgt`, `*.pdf`, `*.php`, `/archive/`,
`/widget/`) overlap with the `/article/<id>/...` URLs or the homepage
this actor uses.

## WAF

`omanobserver.om` shows **no active challenge**. It sits behind
Sucuri/Cloudproxy (`server: Sucuri/Cloudproxy`, `x-sucuri-id: 18002`
response headers present on every request), but `curl_cffi` `chrome124`
gets a clean 200 on the homepage (~780 KB), article pages (~265-270 KB),
and a battery of synthetic-404 tests -- no challenge body, no 403, no
CAPTCHA interstitial observed at any point.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile ladder escalation was needed.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.omanobserver.om/article/<id>/<category>/<subcategory?>/<slug>`

Exactly **one** `<script type="application/ld+json">` block per article,
typed `NewsArticle`, and it **includes `articleBody` directly** -- no HTML
fallback needed. Verified full, untruncated text (641-2754 bytes) across
5 sampled articles spanning hard news (Oman/community), business/energy,
sports (football + "other-sports"), and a podcast-episode page. No
`isAccessibleForFree` field and no "subscribe"/"premium"/paywall markup
found on any sample -- this appears to be a fully open-access site.

Full field set on the `NewsArticle` node: `@context`, `@type`,
`dateCreated`, `datePublished`, `dateModified`, `url`, `headline`,
`description`, `keywords`, `inLanguage`, `mainEntityOfPage`,
`thumbnailUrl`, `image` (an `ImageObject` with `url`/`height`/`width`),
`articleBody`, `author` (a single `Person` object, not a list -- every
sample used either the generic byline "Observer Web Team" or one named
reporter), `publisher` and `copyrightHolder` (both `Organization` nodes,
name "Oman Observer" on every sample).

**Quirk -- unescaped HTML entities in `keywords`:** the `keywords` string
contains literal un-decoded HTML entities, e.g. an apostrophe rendered as
`&#039;` inside `"South,Korea&#039;s,Doosan,wins,..."`. This is the CMS
embedding a real HTML entity directly into the JSON string value -- not a
JSON-escaping problem (`json.loads` already handles standard escapes
correctly). `html.unescape()` is applied defensively to
`headline`/`description`/`articleBody`/`keywords`, mirroring the same
quirk documented for gulfnews-scraper. Note `keywords` itself is not a
curated tag list -- it's the headline's words comma-joined by the CMS
("South,Korea's,Doosan,wins,major,EPC,contract,for,Misfah,power,project"
for a headline "South Korea's Doosan wins major EPC contract for Misfah
power project") -- passed through as-is per raw-passthrough convention,
not filtered or restructured.

**Quirk -- slug/category segments are cosmetic, not routing:** the server
resolves an article purely by the numeric ID in the URL path. Requesting
the correct ID with a deliberately wrong category (`/article/1194837/wrong/
category/totally-wrong-slug-here`) returns HTTP 200 with the identical
article content, and the ld+json `url` field always reflects the TRUE
canonical URL (correct category/slug), not whatever was requested. This
means article URLs scraped from anywhere (including third-party mirrors
with stale slugs) will still resolve correctly as long as the numeric ID
is intact.

### 2. Latest headlines — `S2-html-listing`

No working RSS or sitemap exists:
- `/feed` -> HTTP 404
- `/rss.xml`, `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-index.xml`,
  `/googlenews-sitemap.xml`, `/news-sitemap.xml`, `/sitemap_news.xml`,
  `/sitemap-news.xml`, `/amp-sitemap.xml`, `/sitemaps/sitemap.xml`,
  `/sitemap.xml.gz` -> all HTTP 404
- `/rss` -> returns HTTP **200**, but it is NOT a feed. The CMS renders
  its generic page template for any unmatched route with a 200 status
  (`<body class="OtherPage">`, empty content area, `<h1 hidden>rss -
  oman observer</h1>`) instead of returning a real 404 for unknown
  slugs -- a soft-200, not a soft-404. This is the opposite direction of
  the "soft-404" pattern documented for other outlets in this portfolio
  (business-standard-scraper), so it's worth flagging explicitly: **only
  the `/article/<id>/...` path returns real 404s for bad input; arbitrary
  top-level slugs return a soft-200 empty shell instead.**

Because no feed exists, `GET https://www.omanobserver.om/` (homepage) is
scraped for `<a href>` links matching `/article/(\d+)/...`, the same
homepage-fallback pattern used by chinadaily-scraper and
jamaicagleaner-scraper. 60 unique article links were found on one
homepage fetch, spanning all sections (Oman/community, weather, business,
sports, podcast).

**Quirk -- hero-card anchors glue headline + teaser together:** several
homepage widgets ("hero card" `a.ratioSizeBig` blocks) wrap BOTH a
`div.title` (the headline) AND a `div.description` (a full teaser
paragraph) inside the SAME `<a>` tag. Naively calling `a.get_text()`
concatenates the two into one run-on string (confirmed: first extractor
draft produced `"Al Hamra records Oman's highest rainfall at
28mmMUSCAT: Rainfall of varying intensities..."` for one entry). The fix:
every single article-link anchor sampled (105/105 occurrences across all
homepage widget types -- hero cards, "Most Read" tab-carousel items, and
plain listing rows) carries a clean `title="..."` attribute holding
exactly the headline with no teaser text. The extractor reads
`a["title"]` first and only falls back to `a.get_text()` if an anchor
somehow lacks a `title` attribute.

The numeric article ID is a plain auto-increment primary key (not
date-encoded like chinadaily's hex ID or jamaicagleaner's YYYYMMDD path
segment). Spot-checking 4 IDs spanning Aug 19-25 2026 confirmed the ID
correlates monotonically with `datePublished` (strictly increasing ID =
strictly increasing publish timestamp), so sorting the deduplicated link
set descending by numeric ID reproduces newest-first order without
needing to fetch each article individually. Homepage DOM order does
*not* reliably match ID order (editorial modules mix "top story" and
"most read" placements), so the extractor sorts explicitly rather than
trusting document order.

## Paywall behavior

None observed. No `isAccessibleForFree` field, no paywall overlay markup,
no truncated `articleBody` ("..." cutoffs) on any of the 5 sampled
articles (hard news, business, 2 sports pieces, and a podcast-episode
page).

## 404 behavior

Real HTTP 404s confirmed on `/article/<id>/...` for every synthetic
bad-input case tried: a 10-digit out-of-range ID, an ID one increment
above the current max (not yet published), ID `0`, and a non-numeric ID
(`/article/abc`) -- all four return HTTP 404 with the same generic
~200 KB error-page body, never a 200 with empty/placeholder content. This
is the opposite of the soft-200 behavior seen on `/rss` and other
unmatched top-level slugs (see "Latest headlines" section above) --
article-ID routing specifically enforces a real 404.

## Known limits

- `keywords` is CMS-autogenerated from the headline's words, not curated
  topic tags -- don't treat it as a reliable category/topic signal.
- `author` is always a single `Person`, often the generic "Observer Web
  Team" byline rather than a named reporter -- don't assume it identifies
  an individual journalist.
- `urlCategoryPath` (both modes) is derived from the URL path segments,
  not sourced from upstream ld+json (which has no `articleSection` or
  breadcrumb data at all) -- best-effort only, and category/subcategory
  segment count varies (e.g. podcast episodes have only one segment,
  `podcast`, vs. two for most news/sports articles).
- Latest-mode ordering relies on numeric-ID-correlates-with-recency,
  verified on a small (4-ID) spot-check spanning one week -- not a
  documented upstream guarantee. If the CMS ever migrates to non-sequential
  or UUID-style IDs, this ordering breaks; `UnexpectedShape` will NOT catch
  that (ordering degradation is silent, unlike a shape change), so a
  periodic sanity check (does newest-ID article's `datePublished` still
  look recent?) is worth adding to the diff-cadence checklist below.
- Only 5 articles sampled in depth (community/foreign-affairs, business,
  2 sports, 1 podcast). A structurally different template (e.g. a
  live-blog, photo-gallery, or video-only page) was not sampled -- if one
  lacks `articleBody` in its `NewsArticle` node, `UnexpectedShape` raises
  rather than silently returning nothing.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check: (1) the
`&#039;`-in-`keywords` unescaped-entity quirk, (2) that `/rss` and
sitemap paths are still dead (in case the CMS adds a real feed later,
which would be a strictly better `latest`-mode source), and (3) that
article-ID ordering still correlates with `datePublished`.
