# Crawling Method — Free Malaysia Today

**Last verified:** 2026-08-26

## robots.txt

Independently re-fetched (not just relying on the orchestrator's fast
screen, per the Babak 14 incident). `freemalaysiatoday.com/robots.txt`
returns 200 and gives **`Claude-Web`, `ClaudeBot`, and `anthropic-ai` their
own explicit stanzas**, each `Allow: /` plus `Allow: /_next/` /
`Allow: /videos/`, disallowing only `/wp-admin/`, `/wp-includes/`, `/api/`,
`/video-admin/`:

```
User-agent: Claude-Web
Allow: /
Allow: /_next/
Allow: /videos/
Disallow: /wp-admin/
Disallow: /wp-includes/
Disallow: /api/
Disallow: /video-admin/

User-agent: ClaudeBot
Allow: /
Allow: /_next/
Allow: /videos/
Disallow: /wp-admin/
Disallow: /wp-includes/
Disallow: /api/
Disallow: /video-admin/

User-agent: anthropic-ai
Allow: /
Allow: /_next/
Allow: /videos/
Disallow: /wp-admin/
Disallow: /wp-includes/
Disallow: /api/
Disallow: /video-admin/
```

The generic `User-agent: *` group is also permissive (`Allow: /`, same
disallow list). Only `CCBot`, `Amazonbot`, and `Bytespider` get a blanket
`Disallow: /` -- none of those apply here. No blanket block, no
Claude-specific block. Clear to build.

## WAF

`freemalaysiatoday.com` is fronted by **Cloudflare** (`server: cloudflare`,
`cf-ray` header present on every response) but shows **no TLS-fingerprint
challenge**. `curl_cffi` `chrome124` gets a clean 200 on the homepage,
article pages, and the RSS feed from a home-network IP -- no `cf-mitigated`
header, no "Just a moment" interstitial, no 403.

**IP-reputation gate found during cloud smoke test:** the first `apify
call` (no explicit `proxyConfiguration`, i.e. Apify's default datacenter
egress) failed with `Warmup failed: 403` -- the exact same `chrome124`
request that succeeds from a residential IP is blocked outright from
Apify's shared datacenter IP range. Re-running with
`proxyConfiguration: {"useApifyProxy": true, "apifyProxyGroups":
["RESIDENTIAL"]}` succeeded immediately (`latest mode: -> 3 headlines`,
`exit_code: 0`). This confirms Cloudflare here gates on IP/ASN reputation
*in addition to* TLS fingerprint -- the input schema's `proxyConfiguration`
default is Residential for exactly this reason; do not disable it for this
actor.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-nextdata`

`GET https://www.freemalaysiatoday.com/category/<section>/<yyyy>/<mm>/<dd>/<slug>`

FMT is a **headless WordPress site behind a Next.js frontend** (WPGraphQL
backend, confirmed by `robots.txt` allowing `/_next/static/`,
`/_next/image/`, `/_next/data/`, and the page HTML being littered with
`data-next-head` attributes). **No `<script type="application/ld+json">`
tag of any kind was found on any sampled article page** -- this differs
from most of the portfolio, where ld+json `NewsArticle` is the primary
strategy. The only usable structured source is the `__NEXT_DATA__` script
tag, at `props.pageProps.post`:

```
post.__typename, id, databaseId, title, excerpt (HTML), slug, status,
date (local, e.g. "2026-08-26T09:30:00"), dateGmt, modifiedGmt, uri,
content (raw WordPress HTML -- <figure>/<img>/<p> etc, full article),
author.node.{id,databaseId,name,slug,uri,avatar,jobTitle,sameAs},
categories.edges[].node.{databaseId,name,slug},
tags.edges[].node.{databaseId,name,slug},
featuredImage.node.{databaseId,sourceUrl,altText,caption,mediaDetails}
```

Passed through close to verbatim (raw-passthrough convention). A
flattened `articleBody` plain-text convenience field is added by joining
`<p>` text from `post.content` with BeautifulSoup -- the raw HTML `content`
field is also kept untouched.

**Quirk:** `post.content` HTML entities (curly quotes, em dashes, `&#8217;`
etc) decode correctly to real UTF-8 codepoints in `response.text` --
confirmed by checking the raw response bytes (`\xe2\x80\x9c` for a left
curly quote) and the decoded codepoint (`0x201c`). Console/terminal
printing of those codepoints can look like mojibake (`�`) on a
cp1252-default Windows console -- that is a local print-encoding artifact,
not an upstream data bug. Nothing to work around in the extractor itself.

**404 handling:** a nonexistent slug returns a real **HTTP 404** status
code (verified against a deliberately-invented slug), and `pageProps` on
that response is an empty `{}` (no `post` key at all). The actor checks
`response.status_code == 404` *before* attempting to parse `__NEXT_DATA__`,
so this never reaches the parser as a shape-mismatch crash.

### 2. Latest headlines — `S2-rss`

`GET https://www.freemalaysiatoday.com/feeds/rss/headlines`

Standard RSS 2.0, **50 items per fetch** (richer than most of this
portfolio's 10-item feeds). Unusually rich per item: `title`, `link`,
`dc:creator` (byline present directly on the feed item), `pubDate`,
multiple `<category>` tags (all of them, not just one -- e.g.
`["Super Highlight", "Letters", "Top Opinion", "Opinion", "Highlight"]`),
`guid` (`isPermaLink="true"`, matches `link`), `description` (plain-text
teaser), **`<content:encoded>` carrying the FULL article HTML** (not a
teaser -- verified identical in substance to the article page's
`post.content`), and a `<media:thumbnail url="...">` lead image. Because
`content:encoded` already carries the complete article, the same
`_flatten_html()` helper used for article mode is reused here too, so
`latest` mode records also get a full plain-text `articleBody` field for
free -- not just a headline stub.

No Google News sitemap was probed/needed since the RSS feed already fully
covers the "newest headlines" use case with more data per item than a
sitemap would carry.

## Paywall behavior

None observed. Free Malaysia Today is a free, ad-supported (Google
Publisher Tag / Kiosked scripts observed in `<head>`), general-audience
Malaysian outlet -- no `isAccessibleForFree`/paywall field exists anywhere
in the `__NEXT_DATA__` post object, and no subscribe/paywall overlay was
found in sampled HTML.

## Known limits

- 3 articles sampled in depth (1 opinion/letter, 2 nation/hard-news). All
  three used the identical `props.pageProps.post` shape. A structurally
  different template (photo gallery, video feature, live-blog) was not
  sampled and might carry different `pageProps` keys.
- `categories`/`tags`/`author`/`featuredImage` are kept as their raw
  WPGraphQL nested-edge shape (`{"edges": [{"node": {...}}, ...]}`) rather
  than flattened to plain lists, per the raw-passthrough convention --
  downstream consumers that want a flat list of category names should walk
  `categories.edges[].node.name` themselves (latest-mode `categories` is,
  by contrast, already a flat list of strings, since that's what the RSS
  `<category>` elements naturally give).
- `date`/`dateGmt` on the `__NEXT_DATA__` object are two different values
  (site's local time with no explicit offset vs `Z`-implied GMT) -- both
  are kept verbatim rather than reconciled into one canonical field.

## Diff cadence

Quarterly smoke test recommended.
