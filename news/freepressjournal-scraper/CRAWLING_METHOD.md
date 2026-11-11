# Crawling Method — Free Press Journal

**Last verified:** 2026-08-26

## robots.txt

`https://www.freepressjournal.in/robots.txt` returns 200 with:

```
User-agent: *
Allow: /
Disallow: */cdn-cgi/challenge-platform/*
Disallow: *casino*
Disallow: *online-gaming*
Disallow: *online-gambling*
Disallow: *roulette*
Disallow: *e-gaming*
Disallow: */1000*
Disallow: /newsite/
Disallow: /shell.html
Disallow: */topic/*
Disallow: */search*
Disallow: /*/attachment/*
Disallow: /*/feed
Disallow: /date/*
Disallow: /budget-2019/*
Disallow: /1* ... /9*   (blocks any top-level path starting with a digit 1-9)
Disallow: *?p*
Disallow: */2019/*
Disallow: */page/*
Disallow: */amp/ampstories/*
Disallow: *%*
Disallow: */cmcm/*
Disallow: /brand-focus/*
Disallow: /*/glance
Disallow: */share?url=*
Disallow: *send?text=*
Disallow: *utm_*
Disallow: /topic/*
Disallow: /corporate-gallery/*
Disallow: /corporate-corner/*

Sitemap: https://www.freepressjournal.in/news-sitemap.xml
Sitemap: https://www.freepressjournal.in/daily-news-sitemap.xml
Sitemap: https://www.freepressjournal.in/google-news-sitemap.xml
Sitemap: https://www.freepressjournal.in/amp-stories-sitemap.xml
```

No explicit Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai
disallow anywhere in the file, no blanket `Disallow: /`. Independently
re-verified with a fresh `curl` (not reused from the orchestrator's fast
screen) before any code was written, per this portfolio's policy after the
"Babak 14" incident.

Two rules worth flagging explicitly since they *could* have blocked this
actor's paths and didn't:
- `Disallow: /1*` through `/9*` blocks any URL whose first path segment
  starts with a digit. Free Press Journal's article URLs are always
  `/<section-slug>/<article-slug>` (e.g. `/bhopal/...`, `/education/...`,
  `/lifestyle/...`) -- the section slug is always alphabetic, so this rule
  never matches a real article URL. Confirmed across every sampled article
  and RSS item.
- `Disallow: /*/feed` only matches paths literally ending in `/feed`. The
  latest-mode source used here is `/stories.rss` (a distinct top-level
  path, not `/feed`), so it is unaffected.

Clear to build.

## WAF

`freepressjournal.in` is fronted by **Cloudflare** (`server: cloudflare`,
`cf-ray` present on every response) but presented **no challenge** to plain
`curl_cffi` `chrome124` impersonation during recon: homepage, 3 article
pages spanning different sections (Bhopal, Education, Lifestyle), the
`news-sitemap.xml`, and the `stories.rss` feed all returned clean 200s with
full content -- no "Just a moment"/`challenge-platform`/captcha body
markers, no unexpected 403/429/503.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.freepressjournal.in/<section>/<slug>`

Each article page emits 8 separate `application/ld+json` blocks (many
`SiteNavigationElement` blocks, `BreadcrumbList`, `WebPage`, `ImageObject`,
`NewsArticle`, `NewsMediaOrganization`, `ProfilePage`, `Website`,
`ViewAction`) -- `extract_article` picks out the `NewsArticle` one
specifically. It carries `articleBody` with the **full plain-text article**
(600-1,900 characters across 3 samples), `headline`, `description`,
`keywords` (comma-separated), `articleSection`, `author` (array of `Person`
objects with `name`/`url`), `image` (array of plain URL strings, not
`ImageObject` dicts -- differs from newindianexpress-scraper's shape),
`publisher` (`NewsMediaOrganization` with logo), `contentLocation`,
`associatedMedia` (single lead-image object), `speakable`, and
`isAccessibleForFree`.

This site runs the same **Quintype/AssetType CMS** as other India actors in
this portfolio (`media.assettype.com` image CDN host, `stories.rss` feed
shape identical to newindianexpress-scraper's).

**Paywall check:** `isAccessibleForFree: true` on every sampled article --
no metering/paywall marker detected on Free Press Journal's main news
content.

**Quirk -- truncated `headline`:** the JSON-LD `headline` field is
hard-truncated (no ellipsis) around ~100-110 characters on longer titles.
Confirmed on 2 of 3 sampled articles (the third had a naturally short
headline and was not truncated). Example:

- JSON-LD `headline`: `"MP Nursing College Case: Supreme Court Tells
  Students To Ask Colleges To Face CBI Probe; Exams Allowed At"`
- Actual full headline (from `<title>`/`og:title`, both identical and
  untruncated): `"...Exams Allowed At Cleared Institutions"`

The full headline **is** available on the page (`<title>` and `og:title`
meta tag both carry it verbatim), but per this portfolio's raw-passthrough
convention the JSON-LD `headline` field is passed through as-is rather than
silently repaired from a different source -- documented here and in
`output_schema.json` so downstream consumers know to fall back to another
field if they need the untruncated headline. (Latest-mode `title`, sourced
from RSS, is NOT truncated.)

**Quirk -- static `contentLocation`:** every sampled article's JSON-LD
`contentLocation` carries the same literal value, `{"@type":
"AdministrativeArea", "name": "Mumbai, India"}`, regardless of the story's
actual dateline (a Bhopal-datelined story still carries "Mumbai, India").
This appears to be a fixed publisher-HQ value baked into the CMS template,
not a per-article geotag. Passed through as-is.

**Quirk -- lower-cased `@type` in `associatedMedia`:** the nested
`associatedMedia` object's `@type` is `"imageObject"` (lower-case first
letter) instead of the schema.org-standard `"ImageObject"`. Minor upstream
inconsistency, passed through verbatim.

**Encoding check:** initial recon appeared to show mojibake (`�`) in
`articleBody` around a smart-quote ("green check"). Direct byte-level
inspection of the raw HTTP response confirmed the actual bytes are
`\xe2\x80\x9c`/`\xe2\x80\x9d` (correct UTF-8 for U+201C/U+201D, curly
double quotes) and the response's declared encoding is `UTF-8`
(`Content-Type: text/html; charset=UTF-8`). The apparent mojibake was
purely a Windows terminal codepage rendering artifact when printing to
console during recon, not a real data-quality issue -- no `html.unescape()`
fix or mojibake repair is needed for this outlet.

**404 handling — soft-404, not a real HTTP redirect or status:** a
nonexistent/mistyped article slug returns **HTTP 200** with an **empty
body** (`Content-Length` absent, 0 bytes) and a non-standard response
header `Refresh: 0;url=https://www.freepressjournal.in/404`. This is a
meta-refresh-style redirect delivered via an HTTP header rather than a real
`Location`-based redirect or a `404` status code -- `curl_cffi` (like most
HTTP clients) does not follow `Refresh` headers, only real redirects, so it
surfaces as a 200 with near-zero content length. Confirmed on two different
nonexistent slugs. Since every real article page is 100KB+, `main.py` and
`test_local.py` both check `len(r.content) < 1000` on a 200 response and
classify it as `_error: "not_found"` before attempting JSON-LD extraction
-- this avoids miscategorizing a legitimate 404 as `UnexpectedShape` schema
drift, which would otherwise crash the whole run per this portfolio's
fail-loud convention.

### 2. Latest headlines — `S2-rss`

`GET https://www.freepressjournal.in/stories.rss`

Same Quintype/AssetType CMS feed shape as newindianexpress-scraper's
`stories.rss`: standard `title`/`link`/`guid`/`pubDate`/`description`
(description usually empty) plus `atom:author`/`atom:name`/`atom:uri`
(byline + profile path), `media:keywords` (comma-separated), `category`
(often 2-3 values per item, e.g. `Education`, `Topnews`, `FPJ Shorts`),
`media:content`/`media:thumbnail` (lead image URLs with height/width), and
`content:encoded` (the **full article body as HTML markup**). Confirmed
live with 9 items across several categories in one fetch on 2026-08-26.
Not blocked by robots.txt (`/stories.rss` is a distinct top-level path from
the disallowed `*/feed` pattern).

**Parser note:** BeautifulSoup's `xml` (lxml-xml) parser strips namespace
prefixes from tag names, so `item.find("author")` matches `<atom:author>`,
`item.find("name")` matches `<atom:name>`, `item.find("keywords")` matches
`<media:keywords>`, `item.find("content")` matches `<media:content>`,
`item.find("thumbnail")` matches `<media:thumbnail>`, and
`item.find("encoded")` matches `<content:encoded>`. Verified against a live
downloaded copy of the feed before wiring `extract_rss_items`.

## Paywall behavior

No paywall markers or truncation observed on any sampled article's
`articleBody` (`isAccessibleForFree: true` on all 3 samples).

## Known limits

- `latest` mode returns whatever `stories.rss` currently carries (9 items
  at last check) -- no section-specific feed variants were probed since the
  site-wide feed already spans many sections.
- Article-mode `headline` is truncated on longer titles (see Quirk above);
  the untruncated headline is not carried in this actor's output since it
  would require reaching into a separate HTML source (`<title>`/`og:title`)
  outside the raw JSON-LD passthrough.
- `image` field shape differs between modes: article-mode `image` is a
  list of plain URL strings; latest-mode `image` is a single URL string
  (from `media:content`). Raw passthrough of each source's native shape,
  not normalized.
- `contentLocation` is a static "Mumbai, India" value on every article, not
  a genuine per-article geotag (see Quirk above).

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Free Press Journal redesigns the page, `extract_article`
will raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
