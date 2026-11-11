# Crawling Method — Trinidad Guardian

**Last verified:** 2026-08-25

## WAF

`guardian.co.tt` (served as `www.guardian.co.tt` via CloudFront) shows **no
active WAF challenge**. `curl_cffi` `chrome124` gets a clean 200 on the
homepage (~157 KB) and article pages (~75-90 KB) -- no challenge body, no
403, no `cf-ray`/`x-datadome-cid`/`x-kasada-tier`/`_abck` markers of any
kind. Response headers show plain `nginx` origin behind `CloudFront`
(`x-cache: Hit from cloudfront`), no anti-bot vendor signature.

`robots.txt` is a single block:

```
User-agent: *
Crawl-delay: 10
```

No `Disallow` lines at all (so nothing to check for a multi-group parser
bug -- there's only one group and it has no disallows), no
Claude/GPTBot/anthropic-ai block of any kind, and no `Sitemap:` line
either.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## CDN-edge URL validation (important quirk, not a WAF)

Every article URL ends in a `-6.2.<numericId>.<hash>` suffix (e.g.
`-6.2.2652875.3d3fca7ccb`). The `<hash>` is a signed value CloudFront
validates against `<numericId>` *before* the request ever reaches the
origin: changing the hash (even by one character) while keeping a real,
existing `<numericId>` returns **HTTP 400 "Bad Request"** (an 11-byte
plain-text body, `x-cache: Error from cloudfront`) -- not a 404, and not a
WAF block. The URL's `<slug>` and section prefix (`/business/`, `/news/`,
etc.) are purely cosmetic and are **not** part of the validated portion --
swapping them while keeping a real `<numericId>.<hash>` pair still
resolves to the same article with a normal 200.

Practical effect: it was not possible to construct a synthetic
"real-id-but-deleted-article" 404 to verify origin-level 404 behavior for
this URL shape, because any hand-built id/hash pair that doesn't match a
real article fails CloudFront's edge check first. In practice this means
**any malformed or synthetic article URL a user supplies will almost
always come back as HTTP 400**, and the actor treats HTTP 400 the same as
HTTP 404 -- both map to `_error: "not_found"`. Genuine off-path 404s
(non-article-shaped URLs, e.g. a stale RSS/sitemap guess) were confirmed
as real, consistent 404s: a synthetic unrelated path and every
RSS/sitemap path probed all returned the exact same 53,553-byte custom
404 HTML page.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.guardian.co.tt/<section>/<slug>-6.2.<id>.<hash>`

Sections observed: `news`, `business`, `sports`, `opinion`, `article`
(the last one is used as a catch-all for features/health/lifestyle
columns, not a literal "Article" category).

The page emits exactly **1** ld+json block, typed `NewsArticle`, with:
`headline`, `description`, `dateModified` (RFC-822-style string, e.g.
`"Tue, 25 Aug 2026 07:44:17 -0400"`), `isAccessibleForFree` (emitted as
the **string** `"true"`/`"false"`, not a JSON boolean -- confirmed `true`
on all 5 sampled articles), and `image` (a single `ImageObject` dict, not
an array). **Missing entirely:** `articleBody`, `author`, `datePublished`,
`publisher`.

Full text comes from HTML: `div.ag-article-text` contains a mix of
`<p class="bodytext">`, `<p class="byline">` (a reporter signature block
some writers prepend to their own copy -- e.g. `"PETER CHRISTOPHER"` /
`"Senior Multimedia Reporter"` / `"peter.christopher@guardian.co.tt"` as
3 separate leading paragraphs; other writers, and wire/desk pieces, have
none), and **interleaved `<p class="Caption">` / `<p class="Source">`**
paragraphs that belong to inline images sprinkled through the body, not
the article prose (confirmed on a 60-paragraph feature article: 53
`bodytext`, 3 `Caption`, 3 `Source`, 1 `byline`). Only `bodytext`/`byline`
paragraphs are joined into `articleBody`; `Caption`/`Source` are
explicitly excluded via CSS class selector (`p.bodytext, p.byline`) --
getting this wrong would silently inject "An AI generated image
depicting..." / "AI generated" credit lines into the middle of the
article text.

`author` is pulled separately from the article header's
`div.author > span` element (e.g. `"PETER CHRISTOPHER"`, `"Sport Desk"`).
Confirmed **absent/empty** on some opinion columns (the `.author` div
exists but is empty -- no byline at all, not even in the body text) --
treated as optional, `None` when missing, not raised on.

`datePublished` is **not present in ld+json at all** on this site (unlike
Jamaica Gleaner, whose `Article` block does carry it). It's synthesized
from the article header's `span.textelement-createdtime`
(`YYYYMMDDHHMMSS`, e.g. `20260825074143`), assuming Trinidad & Tobago's
fixed **UTC-4** offset (AST -- T&T does not observe DST, so this is safe
year-round) → `2026-08-25T07:41:43-04:00`. The raw string is kept
alongside as `createdTimeRaw` for anyone who wants to verify or re-derive
it independently. A second, day-precision timestamp,
`span.textelement-publishing.date` (`YYYYMMDD`), is kept as a secondary/
redundant `publishDateRaw` field -- confirmed on one sample to actually
**differ by a day** from `createdTimeRaw`'s date component (created
22 Aug 23:06, published 23 Aug), so it is a genuinely distinct field, not
just a truncation of the other.

`category` is parsed from the URL path's first segment (`news`,
`business`, `sports`, `opinion`, `article`) since there is no
`BreadcrumbList` ld+json block to pull it from.

**Soft-hyphen artifact:** upstream injects U+00AD SOFT HYPHEN characters
mid-word throughout `headline`, `description`, and body text (e.g. raw
HTML/ld+json contains `"Cham­ber"`, `"Se­nior Mul­ti­
me­dia Re­porter"`) -- an invisible line-break-hinting artifact
from the CMS's justified-text renderer, not real content, and normally
invisible when rendered in a browser. All text fields are cleaned of
U+00AD before being emitted; without this, every field would be littered
with invisible characters splitting words apart (which look fine on
screen but silently break tokenization/search downstream).

Verified on 5 samples across 4 sections (business, sports, opinion, and 2
"article"-section feature/health pieces): the `div.ag-article-text` /
ld+json `NewsArticle` shape held in every case.

### 2. Latest headlines — `S2-html-listing`

`GET https://www.guardian.co.tt/` (homepage)

The site has **no RSS feed and no sitemap.xml at all** -- not merely
broken like Jamaica Gleaner's empty stub, but entirely absent. Every path
probed returned a plain 404: `/rss`, `/rss.xml`, `/feed`, `/feed/`,
`/rss/news`, `/sitemap.xml`, `/news-sitemap.xml`, `/sitemap_index.xml`,
`/googlenewssitemap.xml`. The homepage HTML also contains **zero**
mentions of the strings "rss", "sitemap", or "feed" (case-insensitive) --
no `<link rel="alternate">` hint either.

Instead the homepage is scraped for `<a href>` links matching
`/<section>/<slug>-6.2.<id>.<hash>` (37 unique articles found across
5 sections on the sampled fetch: news, business, sports, opinion,
article). Each link appears multiple times in the markup (a full card
with an `<h1 class="headline">`, a bare thumbnail-only anchor, sometimes
a denser "most read"-style widget instance with teaser text and hidden
timestamp spans glued together in `.get_text()` with no separators) --
only the dedicated `<h1 class="headline">` element inside each anchor is
trusted for the title; anchors without one are still followed for the
link/id but don't overwrite an already-found title. (An earlier version
of this extractor took the anchor's full `get_text()` and kept whichever
occurrence was longest, matching the `jamaicagleaner-scraper` pattern --
that broke here because some homepage widgets glue a teaser paragraph and
a raw `YYYYMMDDHHMMSS` timestamp span onto the same anchor with no
separating whitespace, producing garbage like `"...16-year-oldby2026082
5131536The Trinidad and Tobago Police..."`.)

Unlike Jamaica Gleaner, **there is no date embedded in the URL** -- the
numeric CMS content `<id>` (confirmed auto-increment: ids on the sampled
homepage ranged 2651517-2653026, with the top "just published" news item
at the highest id and older opinion pieces at the lowest) is used as a
best-effort recency proxy instead, sorted descending. This is not exact
across sections (business-section ids on the same fetch were
`2652875, 2652873, 2652872, 2652874` in on-page order -- not strictly
monotonic within a section either) but is directionally reliable and is
the only recency signal available without visiting every candidate
article individually.

## Paywall behavior

None enforced. `isAccessibleForFree: "true"` on all 5 sampled
`NewsArticle` blocks (business, opinion, sports, and 2 feature articles).
A cosmetic "Click HERE to Login" / subscribe-for-free upsell block is
present after the article body on every sampled page regardless of the
`isAccessibleForFree` value (it's a sibling `div.ag-block-box`, not
nested inside `div.ag-article-text`, so it's automatically excluded from
`articleBody` by the container scoping) -- matching the cosmetic-paywall
pattern seen elsewhere in this portfolio (LA Times, Vox, Handelsblatt).

## Known limits

- `latest` mode's `articleId`-based ordering is a proxy for recency, not
  a verified timestamp -- fetch the article (`article` mode) for the real
  `datePublished`.
- `datePublished` is synthesized from an HTML span, not ld+json (this
  site has none) -- if the assumed fixed `-04:00` offset is ever wrong
  for a specific article (unlikely; T&T does not observe DST), the raw
  `createdTimeRaw` string is kept so consumers can re-derive it.
- Any malformed/synthetic article URL almost always surfaces as HTTP 400
  (CDN-edge hash validation), not HTTP 404 -- both are treated identically
  as `_error: "not_found"`. See "CDN-edge URL validation" above.
- `author` is legitimately absent on some opinion columns and wire/desk
  pieces -- not a bug, not raised on.
- Only 5 articles sampled in depth (business, opinion, sports, and 2
  "article"-section features/health pieces). A structurally different
  template (live-blog, video feature, photo gallery, e-paper/PDF edition
  content) was not sampled and might lack `div.ag-article-text` entirely
  -- would raise `UnexpectedShape` rather than silently emit a wrong or
  empty record.
- No transient `ConnectionError`/503 flakiness was actually observed
  against `guardian.co.tt` during this recon session (unlike Jamaica
  Gleaner's confirmed intermittent empty-reply issue) -- the retry
  scaffolding in `client.py` is kept per portfolio convention as cheap
  insurance, not because a specific failure mode was reproduced here.

## Diff cadence

Quarterly smoke test recommended.
