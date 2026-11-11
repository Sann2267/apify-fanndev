# Crawling Method — GhanaWeb

**Last verified:** 2026-08-26

## WAF

`ghanaweb.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on the homepage, article pages, and the Google News sitemap. The
site is Akamai-fronted (`x-akamai-transformed` header, mPulse RUM beacon
script in `<head>`, `server-timing: ak_p=...`), but this is CDN/analytics
plumbing only -- no `_abck`/`bm_sz` bot-manager cookie was ever set on any
request, no `cf-ray`, no challenge body of any kind.

`robots.txt` has **three separate `User-agent` groups, each with its own
`Disallow` block directly beneath it** (not a shared/merged block like the
Babak 14 parser-bug pattern flagged in the research doc):

```
User-agent: Mediapartners-Google
Disallow:

User-agent: PetalBot
Disallow: /

User-agent: *
Disallow: /headlines/
Disallow: /GhanaHomePage/classifieds/archive.php
Disallow: /sil/
Disallow: /cdn-cgi/
Disallow: *feedback.php
Disallow: /validate_user.php?url=*

Sitemap: https://www.ghanaweb.com/sitemaps/sitemap.xml
Sitemap: https://www.ghanaweb.com/sitemaps/articles.xml
Sitemap: https://www.ghanaweb.com/sitemaps/news.xml
Sitemap: https://www.ghanaweb.com/sitemaps/videos.xml
```

Each group was checked individually -- no `Claude`, `ClaudeBot`,
`Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token
appears anywhere in the file, under any group. `PetalBot` (Huawei's
crawler) is fully blocked, but that has no bearing on this actor. None of
the `*`-group disallows affect `/GhanaHomePage/NewsArchive/<slug>-<id>`,
`/GhanaHomePage/<section>/<slug>-<id>` article URLs, or the
`/sitemaps/news.xml` feed this actor uses.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.ghanaweb.com/GhanaHomePage/<section>/<slug>-<id>` where
`<section>` is one of `NewsArchive`, `SportsArchive`, `business`,
`entertainment`, `features` (Opinions), and probably others not sampled
(politics/, religion/, diaspora/, etc. share the same site-wide template
per the site's own nav). The trailing numeric `<id>` is the only part that
matters for routing -- GhanaWeb ignores the slug text entirely and
resolves purely on `<id>` (confirmed: `/GhanaHomePage/NewsArchive/xyz-1`
returns a real archived 1995 article; kyivpost-scraper documented the
identical behavior for its own `/post/<id>` routes).

The page emits **one ld+json `@graph` array** (not separate top-level
blocks like kyivpost) holding a `NewsArticle` node and a `BreadcrumbList`
node. `NewsArticle` carries `headline`, `description`,
`datePublished`/`dateModified`, `articleSection` (clean category string,
e.g. `"News"`, `"Opinions"`, used directly instead of parsing the
breadcrumb), `thumbnailUrl`, `image` (object: `url`/`caption`/`width`/
`height`) -- but **no `articleBody`**.

`author` behavior differs by section, and is a real, useful signal:
- News/Sports/Business/Entertainment (staff-written): `author` is a
  `NewsMediaOrganization` object, `name: "GhanaWeb"`, carrying a
  `noBylinesPolicy` link -- the site's declared policy of not crediting
  individual reporters in structured data.
- Opinions/Features (columnist-written): `author` is simply `null`.

Full text comes from HTML: `div.article-content-area`. Like
globaltimes-scraper's Global Times template, this legacy CMS does not
wrap paragraphs in `<p>` tags -- the whole body is one `<p>` with `<br>`
tags separating lines. In-body keyword mentions (e.g. a person's name)
are auto-linked to `/GhanaHomePage/people/person.php?ID=<n>` profile
pages, sometimes preceded by several *empty* duplicate `<a>` tags before
the one carrying the visible anchor text -- a plain `BeautifulSoup
get_text()` walk reconstructs the sentence correctly regardless, since
text nodes are concatenated in document order with no separator inserted
(verified: `"The " + <a>Parliament</a> + "ary Appointments Committee..."`
reconstructs to `"The Parliamentary Appointments Committee..."`).

**Key quirk -- trailing byline-signature + promo noise:** every sampled
staff-written article (News/Sports/Business/Entertainment) ends its real
body with a standalone 2-part reporter/editor-initials line matching
`^[A-Z]{1,5}/[A-Z]{1,5}$` (observed: `"MRA/MA"`, `"DR/MA"`, `"JHM/EB"`,
`"SB/MA"`) immediately followed by an unrelated "watch this other story"
bold-linked headline and a YouTube-embed `<iframe>` or an embedded tweet's
fallback text -- none of which is part of the article. The extractor
detects the first `<br>`-delimited paragraph matching that regex,
captures it as `reporterInitials`, and truncates `articleBody` there.
Content genuinely embedded *within* the narrative and appearing *before*
the signature line (e.g. a quoted tweet's text, or one inline "related
article" link title used as an in-body callout) is kept as part of
`articleBody` -- distinguishing "narrative embed" from "trailing promo"
programmatically beyond the signature-line cutoff was not attempted; see
Known limits.

Opinions/Features pieces (verified on a sampled columnist piece, "My open
advice to new Majority Leader James Agalga") have **no** such signature
line and **no** trailing promo -- the body ends naturally and the full
paragraph list is kept when no signature line is found.

A separate `<p class="floatRight"><strong>Label: </strong><a>Name</a></p>`
element (a sibling of the body, outside the ld+json) carries the only
individual-name byline GhanaWeb exposes:
- `"Source: www.ghanaweb.com"` on staff pieces (self-attributed, matches
  the `noBylinesPolicy` seen in ld+json).
- `"Columnist: <Name>"` on opinion pieces (e.g. `"Columnist: Dr
  John-Baptist Naah"`) -- this is the **only** place an individual
  columnist's name appears; ld+json `author` is `null` for these.

Captured as `bylineLabel` / `bylineName`.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.ghanaweb.com/sitemaps/news.xml`

Google News sitemap, advertised via `Sitemap:` in `robots.txt`. Observed
updating in **near-real-time** -- the freshest item on a live fetch was
published under a minute before the request. Standard shape: `loc`
(article URL), `news:title`, `news:publication_date` (ISO-8601 with
timezone), `news:language`. No `news:keywords` element on this feed
(unlike Global Times' `/sitemap.xml`). `section` is derived from the URL
path segment immediately after `/GhanaHomePage/` (e.g. `NewsArchive`,
`SportsArchive`, `business`, `entertainment`) since the feed itself
carries no explicit category field.

No RSS feed was found: `/feed`, `/rss`, `/rss.xml`,
`/GhanaHomePage/NewsArchive/rss.php`, and `/rss/news.xml` were all probed
and returned 404 (`/feed` resolved to a dead `photos.ghanaweb.com`
subdomain that doesn't even resolve in DNS). The Google News sitemap is
therefore both the only viable `latest`-mode source found and, being
near-real-time, a strong one -- no fallback tier needed.

`sitemap.xml` (the top-level sitemap index in `robots.txt`) is a
site-structure sitemap (category/section landing pages, ~330 KB) and is
not useful for `latest` mode; `news.xml` was the correct pick.

## Paywall behavior

None observed. Free, ad-supported portal; no "subscribe"/"paywall"/
"premium"/"member-only" marker found in raw HTML on any sampled page, and
no `isAccessibleForFree` flag is even emitted in ld+json (unlike
kyivpost/aftonbladet) -- consistent with a site that has no metering
product at all.

## Known limits

- `articleBody` truncation relies on the `^[A-Z]{1,5}/[A-Z]{1,5}$`
  reporter-initials signature line as the boundary between real content
  and trailing promo. On the 5 staff-written samples checked in depth
  (2 NewsArchive, 1 SportsArchive, 1 business, 1 entertainment) this
  signature was present and correctly bounded the real text every time.
  If GhanaWeb ever stops emitting it on some article, the trailing
  "watch this other story" promo/embed would leak into `articleBody`
  uncaught (this is a soft degradation, not a crash -- no
  `UnexpectedShape` is raised for a missing signature, since Opinions/
  Features pieces legitimately have none).
- One sampled article had a single inline "related article" link
  (its title, no surrounding sentence) appear as its own paragraph in
  the middle of the real body, ahead of the signature line -- it was kept
  as-is rather than filtered, since distinguishing a deliberate in-body
  callout from paragraph-shaped noise would need a denylist of URL
  patterns and risks removing genuine content. Documented, not fixed.
- 404 vs 410: a completely malformed path (no trailing numeric ID) returns
  a real HTTP 404; a syntactically valid path with a numeric ID outside
  the currently-valid range (deleted, or higher than any issued ID)
  returns **HTTP 410 Gone**, not 404. Both are treated as `_error:
  "not_found"` by this actor. Low, very old numeric IDs (e.g. `-1`) still
  resolve to real 1995-era archived articles, confirmed via `.../xyz-1`
  returning "THE LEAGUE TABLE AS AT APRIL 25, 1995" -- so don't assume
  low IDs are invalid.
- Only 6 articles sampled in depth (4 staff News/Sports/Business/
  Entertainment pieces, 1 Opinions/Features columnist piece, plus the
  1995 archive spot-check). A structurally different template (photo
  gallery under `/GhanaHomePage/cartoon/`, video feature, live-blog) was
  not sampled and might not fit the `div.article-content-area` selector.
- `bylineName` on staff pieces is always the literal string
  `"www.ghanaweb.com"` (the site attributing content to itself, per its
  `noBylinesPolicy`) -- it is not an individual reporter's name. Use
  `reporterInitials` if you need a (non-identifying) per-article
  attribution signal for staff content.

## Diff cadence

Quarterly smoke test recommended.
