# Crawling Method — Leadership (Nigeria)

**Last verified:** 2026-08-26

## WAF

`leadership.ng` sits behind **Cloudflare** (`server: cloudflare`, `cf-ray`
present) but shows **no active JA3/TLS-fingerprint challenge** for normal
traffic. Plain `curl`/`requests` already gets a clean 200 on the homepage,
article pages, and `/feed/` -- confirmed again with `curl_cffi` `chrome124`
for consistency with the portfolio-wide default. No "Just a moment..."
interstitial, no `cf-mitigated` header, no stale-edge-cache quirk (unlike
`premiumtimesng.com`) observed on the samples checked.

`robots.txt` is a small custom block, not the usual stock Yoast SEO one
seen on other WordPress outlets in this portfolio:

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://leadership.ng/sitemap_index.xml
```

Allow-all for everything except `/wp-admin/` -- no Claude/ClaudeBot/
Claude-Web/Claude-SearchBot/anthropic-ai disallow of any kind, and only one
`User-agent: *` group (no multi-group parser trap to worry about here).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://leadership.ng/<slug>/`

The page emits **one** `<script type="application/ld+json">` block -- a
Yoast-style `@graph` array of cross-referenced nodes: `Article`,
`NewsMediaOrganization`/`Organization`, `WebSite`, `ImageObject`,
`BreadcrumbList`, `WebPage`.

The `Article` node's `author` field is an **inline object**
(`{"@type":"Person","name":"..."}`), matching `punchng.com`'s pattern, not
premiumtimesng.com's bare `{"@id": "..."}` reference. `publisher` and
`image`, however, **are** bare `{"@id": "..."}` references that must be
resolved against sibling nodes in the same `@graph` -- an `Organization`
node (`name: "Leadership Newspapers"`) and an `ImageObject` node
(`url`/`width`/`height`) respectively. The extractor builds an
`@id -> node` index and resolves both, plus re-uses the same resolver for
`author` for robustness against a future shape change.

**No `thumbnailUrl`, `wordCount`, or `commentCount` field exists anywhere
in the graph** on this site -- confirmed absent across 3 sampled articles
spanning News/Entertainment/Business templates. `image` (resolved from the
`ImageObject` node) is used in its place. `keywords` is present on some
articles (a single string, e.g. `"Davido"`) and absent on others (no
`keywords` key at all) -- not every article gets one. `articleSection` is
always a **single string** (e.g. `"News"`, `"Business"`), never a list,
unlike `premiumtimesng.com`/`punchng.com`.

Text values inside this JSON are **proper JSON-Unicode-escaped**, e.g. the
Dayo Amusa headline's apostrophe is the literal JSON escape `"Ogogo’s
Death"`, which `json.loads` decodes correctly on its own -- **not**
double-HTML-escaped like `premiumtimesng.com`'s `&#8217;`-inside-a-JSON-
string pattern. `html.unescape()` is still applied to every text value
pulled from the graph as a no-op safety net, matching the rest of the
portfolio's defensive pattern, but it isn't strictly required here.

Full body text comes from HTML: `div.entry-content > div.content-inner`,
**direct-child `<p>` tags only** (`recursive=False`). Confirmed this
selector matches exactly ONE element per article page, and produces clean
text (11 real paragraphs, no ad/promo leakage) on all 3 samples (Music/
News, Society/News, Business). Ad slots (`div.code-block-N` -- Google
Publisher Tag / `googletag` containers) and the floating share bar
(`div.jeg_share_button`) are sibling, non-`<p>` elements at that same
level, so they're excluded automatically without a denylist.

`description` is pulled from `<meta name="description">` (confirmed
present on every sample), falling back to the ld+json `WebPage` node's own
`description` field if the meta tag is ever missing.

### Soft-404 quirk — the homepage's own `@graph` has an `Article` node too

Deleted/never-existed slugs 200-OK to the **homepage** instead of a real
404 (confirmed on a deliberately-invented slug: final response is the
literal homepage HTML, same title, same byte size as a direct homepage
fetch). This matches `premiumtimesng.com`'s soft-404 pattern -- **but** the
naive "no `Article` node in the graph" detection used on
`premiumtimesng.com`/`punchng.com` does **not** work here: the homepage's
own `@graph` carries an `Article` node describing the front page itself
(`headline` = the site's `<title>` text, `author.name: "Web"`,
`mainEntityOfPage` pointing at `https://leadership.ng/#webpage`).

The real, reliable tell: resolve the `Article` node's `mainEntityOfPage`
`{"@id": ...}` reference to its `WebPage` node, and compare that node's own
`url` field against the requested article URL. On a real article page they
match (e.g. both
`https://leadership.ng/davido-wizkid-burna-boy-lead-2026-headies-nominations/`).
On the soft-404 fallback, the resolved `WebPage.url` is
`https://leadership.ng/` while the requested URL was the invented slug --
a clear mismatch. `extract_article()` raises `ArticleNotFound` in this
case, and `main.py` converts it to a normal `_error: "not_found"` record,
same as a real 404 from the caller's point of view.

### 2. Latest headlines — `S2-rss`

`GET https://leadership.ng/feed/` (optionally `?paged=N` for more)

Standard WordPress default feed. Returns exactly **10 items per page**,
confirmed paginable via `?paged=2` with no overlap/duplication between
pages (checked guids across 2 consecutive pages). `fetch_latest()` walks
`?paged=N` automatically until it has enough items for the requested
`limit` (max 50, i.e. up to 5 pages), deduping by `guid`.

Fields: `title`, `link`, `dc:creator` (a **real per-article byline** that
matches the ld+json `author.name` on the corresponding article page --
confirmed on the Davido/Wizkid/Burna Boy item, `"Zuleihat Chatta"` on both
-- unlike `punchng.com`'s constant `"Punch Newspapers"` placeholder), a
single `<category>` per item, a `guid` (`?p=<id>`), `pubDate`, a teaser
`description` (plain text inside CDATA, HTML-entity-escaped, e.g. `&#160;`
/ `&#8230;`, ending in a `"... [&#8230;]"` truncation marker -- no
"appeared first on ..." boilerplate, unlike `premiumtimesng.com`).

Unusually rich for a "latest" feed on this portfolio: each `<item>` also
carries a full-text **`<content:encoded>`** block with the complete
article HTML (`<p>` tags, matching what's on the live page). This is
passed through raw as `content`, plus a flattened plain-text `articleBody`
convenience field (paragraphs joined with `BeautifulSoup`), so `latest`
mode already returns the full story text without a second `article`-mode
request -- confirmed identical body text between the RSS `content:encoded`
and the live article page's `div.entry-content > div.content-inner` for
the Davido/Wizkid/Burna Boy sample.

No `<enclosure>` or `<media:thumbnail>` tag exists on this feed, so no
per-item lead image is available in `latest` mode (use `article` mode's
`image` field for that).

The `sitemap_index.xml` -> `post-sitemap<N>.xml` (15 dated sub-sitemaps
observed) was also confirmed present, but `/feed/` was chosen as the
primary `latest`-mode source since it carries richer fields (author,
category, description, full body) in one request and supports easy
pagination for `limit` up to 50.

## Paywall behavior

None observed. No "paywall"/"subscribe-wall"/"metered"/"Subscribe to
continue" markers found in raw HTML on any sampled page. Leadership is a
free, open-access site.

## Known limits

- 404s for deleted/never-existed slugs are **soft-404s**, not real HTTP
  404s: the server returns `HTTP 200` with the **homepage's own HTML**.
  The naive "absent Article node" check used elsewhere in this portfolio
  is insufficient here (the homepage has its own Article node) -- the
  extractor instead compares the resolved `WebPage.url` against the
  requested URL (see above).
- `keywords` is absent on most sampled articles (present on only 1 of 3) --
  treated as optional, not raised on if missing.
- Only 3 articles sampled in depth (Entertainment/Music, Society/
  Entertainment, Business), plus the RSS feed (2 pages) and a soft-404
  probe. A structurally different template (e.g. a live-blog, video
  feature, or photo-gallery page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
