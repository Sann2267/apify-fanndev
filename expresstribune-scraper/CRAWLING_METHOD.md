# Crawling Method — The Express Tribune

**Last verified:** 2026-08-25

## WAF

`tribune.com.pk` shows **no active challenge on real content** -- `curl_cffi`
`chrome124` gets a clean 200 on the homepage, real `/story/<id>/...`
article pages, and the latest-articles sitemap.

**Important quirk — targeted anti-enumeration rule.** Cloudflare runs a
rule scoped specifically to the `/story/<id>/...` URL pattern: any
`/story/` URL whose numeric ID does not correspond to a real article
returns an immediate 403 "Just a moment..." challenge page -- even though
the exact same TLS profile gets a clean 200 on real `/story/` URLs seconds
before and after (confirmed: fetched a real article, then a synthetic
`/story/1/test`, then the same real article again -- only the synthetic
ID triggered the challenge; the session was not "poisoned" by it). A
random nonexistent path that does NOT match `/story/<id>/...` (e.g. a
made-up slug at the site root) does **not** trigger this -- it soft-404s
by rendering the homepage/HTML shell (HTTP 200, same byte length as the
real homepage).

Practical effect: this actor cannot distinguish "genuinely deleted
article" from "Cloudflare anti-enumeration block" from the HTTP response
alone -- both look identical (403 + "Just a moment" body). `client.py`'s
existing block-marker detection already catches this and retries
(harmlessly -- retrying does not help, since the block is deterministic
per-URL rather than transient, but it's consistent with portfolio
convention and doesn't hang). After `MAX_RETRIES`, `main.py` emits
`_error: "blocked_or_transient"` for that URL rather than `not_found`,
and the run continues normally for the rest of the input list.

`robots.txt` (`User-agent: * / Disallow:` -- fully open) has no
Claude/GPTBot/anthropic-ai disallow.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html[<template>]`

`GET https://tribune.com.pk/story/<id>/<slug>`

The page emits a single `NewsArticle` ld+json block (`headline`,
`description`, `datePublished`, `dateModified`, `author`, `publisher`,
`image`) -- but **no `articleBody`**.

**Two different CMS body templates were found across samples**, with no
shared class between them:
- Hard-news/business articles: `div.express-parent-div` (confirmed on a
  finance/markets story).
- Long-form opinion/fiction pieces: `div.custom-row` (confirmed on a
  short-story feature) -- a more generic class name, kept as a named
  fallback rather than the primary selector since it's less specific.

The extractor tries `express-parent-div` first, falls back to
`custom-row`, and raises `UnexpectedShape` if neither is present (rather
than guessing at a third, unverified selector). The `_source` field
records which template matched (`S1-html[express-parent-div]` or
`S1-html[custom-row]`) so downstream consumers can see which path was
used.

Trailing boilerplate paragraphs on the hard-news template (`"COMMENTS"`,
`"Comments are moderated and generally will be posted..."`, `"For more
information, please see our Comments FAQ"`, the closing copyright
notice starting `"This material may not be published, broadcast,
rewritten,..."`) and inline `"Read More: ..."` related-article link
paragraphs (seen on a different sample) are filtered by exact-match/
prefix. The opinion/fiction template's own closing author note (e.g. "The
writer can be reached at...") was left in as real editorial content, not
filtered.

**Known upstream data-quality issue (not a parsing bug):** the ld+json
`headline` and `description` fields have been observed with a stripped
apostrophe (e.g. `"PSX ends lower despite Moody s upgrade"` instead of
`"Moody's upgrade"`) -- verified against the raw ld+json bytes on the
wire, this is genuinely how the site serves it, not an encoding/unescape
bug on this actor's side. Passed through raw per portfolio convention
rather than "corrected" (which would risk guessing wrong on a different
case).

### 2. Latest headlines — `S2-sitemap`

`GET https://tribune.com.pk/sitemap/latest-1.xml`

Advertised via `Sitemap:` in `robots.txt`. A plain XML sitemap
(`loc`/`lastmod`/`changefreq`/`priority` only -- **no `news:title` or any
title field**), already newest-first by document order. Since there's no
title in the sitemap itself, a readable title is derived from the URL
slug (last path segment, hyphens replaced with spaces, title-cased) --
this is a cosmetic approximation, not the real headline; use `article`
mode against `link` for the actual `headline` field.

`/feed` returns 403 (WAF-blocked, unrelated to the article-ID rule
above); `/rss`, `/rss.xml`, and `/feeds/rss` all return HTTP 200 but are
**not real feeds** -- they render the homepage/HTML shell (confirmed:
identical byte length to the real homepage), not XML.

## Paywall behavior

None observed. Fully open-access on all sampled articles (hard-news,
finance, opinion/fiction).

## Known limits

- A genuinely deleted/nonexistent article ID cannot be distinguished from
  a Cloudflare anti-enumeration block -- both surface as `_error:
  "blocked_or_transient"`, not `"not_found"`. See the WAF section above.
- `latest` mode titles are derived from the URL slug, not a real title
  field in the sitemap -- fetch `article` mode for the actual `headline`.
- Only two body templates were sampled (hard-news/business,
  opinion/fiction). A structurally different page type (live-blog,
  photo-gallery, video) was not encountered and would raise
  `UnexpectedShape` rather than silently emit a wrong or empty record.
- Upstream apostrophe-stripping in `headline`/`description` (see above)
  is a real site-side data quality issue, passed through as-is.

## Diff cadence

Quarterly smoke test recommended.
