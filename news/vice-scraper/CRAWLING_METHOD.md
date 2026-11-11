# Crawling Method — VICE

**Last verified:** 2026-08-24

## WAF

`vice.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the site-wide RSS feed -- no
challenge body, no 403.

`robots.txt` has no Claude/GPTBot/anthropic-ai disallow.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.vice.com/en/article/<slug>/`

**Two separate `application/ld+json` script tags** are present per article:

1. A generic SEO-plugin `@graph` array (`Article`, `WebPage`,
   `ImageObject`, `BreadcrumbList`, `WebSite`, `Organization`, `Person`
   nodes) -- note the type here is `Article`, not `NewsArticle`. Not used
   by this extractor.
2. A **standalone** dict (not wrapped in `@graph`) with `"@type":
   "NewsArticle"` -- carries `headline`, `author` (list of `{"@type":
   "Person", "name": ...}`), `creator` (redundant plain-string list of the
   same names), `keywords`, `articleSection`, `image`, `datePublished`,
   `dateModified`. **No `articleBody` and no `description` field.**

The extractor scans all `ld+json` blocks and picks the standalone
`NewsArticle` dict specifically (checking `data.get("@type") ==
"NewsArticle"` on each top-level parsed object, not descending into
`@graph` for this one).

`description` comes from `meta[property="og:description"]` instead.

Full text: `div.entry-content` (WordPress Gutenberg content, carries
`wp-block-post-content` class). Body paragraphs are `<p
class="wp-block-paragraph">` tags; ad slots are separate empty
`<div class="code-block">` wrappers (verified empty -- `<div
class="lngtd-dynamic-inarticle">` placeholder with no text) and video
embeds are separate `<div class="wp-block-savage-platform-primis-video">`
elements -- neither contains nested `<p>` tags, so collecting all `<p>`
within `div.entry-content` cleanly excludes both without extra filtering.

### 2. Latest headlines — `S2-rss`

`GET https://www.vice.com/en/rss`

Standard WordPress default feed, 10 items per fetch. `description` is
HTML-entity-escaped HTML ending in a literal WordPress "excerpt" boilerplate
sentence -- `"...&lt;/p&gt;&lt;p&gt;The post &lt;a href=...&gt;Title&lt;/a&gt;
appeared first on &lt;a href=...&gt;VICE&lt;/a&gt;.&lt;/p&gt;"`. Unescaped
and tag-stripped by the extractor (same approach as `philstar-scraper`'s
`description` fix), but the "appeared first on VICE" text is deliberately
kept -- it's real WordPress-generated feed content, not an encoding
artifact to discard. `content:encoded` carries the full body HTML
(also unescaped, kept as HTML rather than stripped, since latest mode
elsewhere in the portfolio -- e.g. `foxnews-scraper` -- also returns
`contentHtml` when the feed provides it for free).

## Paywall behavior

None observed. VICE (post-2023 relaunch, ad-supported) has no subscription
product visible in the sampled article's ld+json or HTML -- full body text
was present and untruncated.

## Known limits

- Only 1 article sampled in depth (Life/Science section). Other sections
  (the site currently publishes a narrower range post-restructuring) were
  only spot-checked via the RSS link list.
- The first (`@graph`, generic `Article` type) ld+json block is ignored
  entirely -- if VICE ever removes the second standalone `NewsArticle`
  block and only keeps the generic one, this extractor would need to fall
  back to reading fields from the `Article` node inside `@graph` instead.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check that the
standalone `NewsArticle` ld+json block (the second script tag) is still
present -- this is the more fragile of the two ld+json sources on this
site and the one this extractor actually depends on.
