# Crawling Method — Fox News

**Last verified:** 2026-08-24

## WAF

`foxnews.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the site-wide RSS feed -- no
challenge body, no 403.

`robots.txt` is minimal (301 bytes) with **no Claude/GPTBot/anthropic-ai
disallow** -- notably unlike several other major US outlets screened in
this same session (CNN, Politico, The Hill, USA Today, and Boston Globe
all explicitly block Claude/anthropic-ai by name in their `robots.txt`).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.foxnews.com/<section>/<slug>`

A single `application/ld+json` script tag holds a `@graph` array
(`WebSite`, `NewsMediaOrganization`, `WebPage`, `NewsArticle`,
`ImageObject`, `VideoObject`, `Person` nodes) -- **note:** the script tag
carries an extra `data-n-head="ssr"` attribute before `type=`, so a naive
regex assuming `<script type="application/ld+json">` as a fixed prefix
fails to match; `BeautifulSoup.find_all("script", attrs={"type":
"application/ld+json"})` (attribute-based lookup, order-independent) is
required instead.

The `NewsArticle` node **includes `articleBody` directly** (full text, not
a teaser -- verified: `wordCount: 517` matched a `articleBody` of
consistent length) -- no HTML fallback needed, unlike most of this
portfolio. Also carries `isAccessibleForFree` as a **real JSON boolean**
here (`true`/`false`), not a string like several other sites (Jakarta
Post, Business Standard) -- and a nested `author` object
(`{"@id": ..., "name": ..., "url": ...}`).

### 2. Latest headlines — `S2-rss`

`GET https://moxie.foxnews.com/google-publisher/latest.xml`

Google Publisher feed on a separate subdomain (`moxie.foxnews.com`), ~25
items per fetch. Unusually rich for a "latest" feed: carries `<content:
encoded>` with the **full article HTML body already inline** (single
HTML-entity-escaped, standard RSS convention -- `&lt;p&gt;...&lt;/p&gt;`
unwrapped transparently by the XML parser into real `<p>` tags as text),
so `latest` mode here returns substantially more than just headlines. Also
carries many `<category>` tags per item -- a mix of internal taxonomy UUIDs
(e.g. `5452c0ee-ae7b-520f-9fa6-6de7ee05a079`) and human-readable labels
(`"Fox News"`, `"fox-news/sports/nba"`) -- passed through as a flat list,
no attempt made to separate UUID vs label since both come from the same
upstream field with no distinguishing marker.

## Paywall behavior

None observed. `isAccessibleForFree: true` on the sampled article, and
`articleBody` was full-length and untruncated. Fox News Digital
(`foxnews.com`) is free/ad-supported; the paid product ("Fox Nation") lives
on a separate domain not touched by this actor.

## Known limits

- Only 1 article sampled in depth (politics/media section). If a different
  section (opinion, lifestyle) structures the ld+json differently, this
  extractor would raise `UnexpectedShape` rather than silently return
  nothing.
- `keywords` field passthrough was not deeply verified for consistency
  across sections -- treated as raw passthrough per portfolio convention,
  no assumptions made about its shape.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check that the
`@graph` array still contains a `NewsArticle` node with `articleBody`
inline -- if Fox News ever moves to a metadata-only ld+json (matching the
more common pattern elsewhere in this portfolio), an HTML fallback
selector would need to be added.
