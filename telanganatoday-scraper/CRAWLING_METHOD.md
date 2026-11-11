# Crawling Method — Telangana Today

**Last verified:** 2026-08-26

## robots.txt

Independently re-fetched and re-verified (`curl_cffi` `chrome124`) before any
code was written, per the standing "Babak 14" incident requirement — did not
rely on the orchestrator's fast screen result.

- `https://telanganatoday.com/robots.txt` returns 200, `content-type:
  text/plain`, served through CloudFront (`x-cache: Hit from cloudfront`).
- `User-agent: *` carries `Allow:/` plus a set of narrow `Disallow:` rules
  (`/wp-admin/`, search/query-string crawl traps, `*/category/*`, `*/amp`,
  `*/tags/*`, `/telangana-amp/`, etc. — the block is duplicated verbatim
  twice in the file, a copy-paste artifact upstream, not a parsing risk) —
  no blanket `Disallow: /`.
- `User-agent: Googlebot` is explicitly granted `Allow: /`.
- **No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-SearchBot`, or
  `anthropic-ai` user-agent block anywhere in the file.**
- Notably, the file *does* explicitly disallow three other AI crawlers:
  `User-agent:  CCBot` (Common Crawl), `GPTBot`, and `ChatGPT-User` (both
  OpenAI) each get `Disallow: /`. Claude-family agents are conspicuously
  absent from that block list — verified by reading the full file text, not
  inferred from absence of a blanket rule.
- Four sitemaps declared: `sitemap_index.xml`, `news-sitemap.xml`,
  `category-sitemap.xml`, `page-sitemap.xml`.

Verdict: clear to build.

## WAF

None detected. `curl_cffi` `chrome124` returned 200 on the homepage, two
sampled article pages, `/robots.txt`, `/feed`, `/news-sitemap.xml`, and a
deliberately-wrong slug (correctly resolved to HTTP 404 via a redirect to
`/404.html`, not silently swallowed or blocked) — no `cf-ray`, no
`x-datadome`, no `_abck`/PerimeterX cookies, no challenge body, no 429/503.
Response headers show `server: nginx/1.24.0 (Ubuntu)` behind CloudFront
(`x-cache: Miss/Hit from cloudfront`) — a CDN, not a bot-management WAF.
`www.telanganatoday.com` redirects to the bare `telanganatoday.com` host.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://telanganatoday.com/<slug>`

Each article page emits 6 separate `application/ld+json` blocks
(`ItemList`, `WebPage`, `Organization`, `WebSite`, `NewsArticle`,
`BreadcrumbList`) — the extractor picks the `NewsArticle` one specifically.
It carries `articleBody` with the **full plain-text article** (confirmed
1,500+ characters on both samples, `\r\n\r\n` paragraph breaks preserved),
`headline`, `description`, `keywords` (comma-separated string, not an
array), `author` (single `Person` object with `name`+`url`, e.g.
`{"name": "PTI", "url": ".../author/PTI"}` for wire-service credit or a
named byline for staff-written pieces), `publisher`, `image`/`thumbnailUrl`,
`mainEntityOfPage`, and `datePublished`/`dateModified`/`dateCreated`.

This site's `NewsArticle` shape is noticeably leaner than sibling South-India
portfolio actor `deccanchronicle-scraper`: **no `alternativeHeadline`, no
`about` (topic array), no `articleSection`/`genre`** fields at all — those
keys are simply absent, not null. The output schema documents only the
fields actually observed; `additionalProperties: true` covers anything
upstream adds later.

**Quirk — non-standard date format:** `datePublished`/`dateModified`/
`dateCreated` are formatted as `"2026-08-26 01:02:30 +05:30"` — **space**
between date and time, not the ISO 8601 `T` separator most other portfolio
sites' JSON-LD uses (e.g. Deccan Chronicle's `"2026-08-26T07:09:51+05:30"`).
Passed through raw, unmodified, per the raw-passthrough convention — no
reformatting attempted.

**Quirk checked and ruled out — JSON-LD control characters:** unlike Deccan
Chronicle (which needed a `strict=False` `json.loads` fallback for a literal
tab character in `articleBody`), both Telangana Today samples parsed cleanly
under `strict=True`. The `strict=False` retry path is kept in
`extractor.py::_parse_ld_json` anyway as a cheap safety net, but was not
required to make either recon sample work.

**Not a quirk (ruled out):** `India's`/`Bhagwat's`-looking `�` characters
seen in raw Windows-console output during recon were confirmed via raw byte
inspection to be correctly-encoded UTF-8 (`\xe2\x80\x99`, the right single
quotation mark U+2019) — a console rendering artifact, not a data problem.
Likewise the RSS `<title>` entity `&#8217;` renders the same way and is
fine as-is.

No `isAccessibleForFree`/`hasPart` paywall-signal fields were observed on
either sampled article, and no paywall/meter/subscriber-only markup was
found in either page's raw HTML. No `__NEXT_DATA__` was found — this is a
traditional WordPress server-rendered page, not Next.js.

### 2. Latest headlines — `S2-rss`

`GET https://telanganatoday.com/feed`

Standard WordPress RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`,
`guid`, `pubDate`, `description`, `category` (single value on sampled
items, e.g. `"India"`, `"Hyderabad"`), `dc:creator` (byline or wire credit
— `"PTI"`, `"Telangana Today"` for staff pieces), and `content:encoded`
(full article HTML — a lead `<figure>` image plus `<p>` paragraphs, same
text as `articleBody` on the article page).

This is a **single site-wide feed** covering all sections, no
section-parameter needed for full latest-mode coverage — confirmed live and
chronological on 2026-08-26 (`lastBuildDate` matched wall-clock time, newest
item ~minutes old at fetch time). One difference from Deccan Chronicle's
`/rss.xml`: this feed returns **500 items per fetch** (~1.9MB response) —
noticeably larger than most portfolio feeds — but the extractor slices to
the requested `limit` after parsing, so this only affects per-run parse
cost, not output shape.

## Paywall behavior

No paywall markers, truncation, or subscriber-only gating observed on either
sampled article. Telangana Today appears to be a fully free, ad-supported
site.

## Content overlap with `deccanchronicle-scraper`

Both actors cover Telangana/Hyderabad-region news, but they are
**independently operated publishers** with separately-authored editorial
content — Deccan Chronicle is a Chennai/Hyderabad-based English daily
(Deccan Chronicle Holdings), while Telangana Today is a Telangana-focused
regional English daily. The only overlap observed is the expected
wire-service layer (PTI/ANI credited articles), which is common across
nearly every outlet in this portfolio and not unique to this pair — the
staff-written Telangana/Hyderabad-specific stories (e.g. the HC judge
reinstatement sample above) are not duplicated between the two sites.
Building this actor is consistent with the portfolio's existing pattern of
multiple India-regional outlets per state/region.

## Known limits

- `keywords` is a comma-separated string in the JSON-LD, not an array —
  passed through as-is, not split.
- `datePublished`/`dateModified`/`dateCreated` use a non-standard
  space-separated (not `T`-separated) date format; passed through raw.
- No `articleSection`/`genre`/`about` fields exist in this site's JSON-LD at
  all (present on some sibling portfolio sites, absent here) — not a bug,
  just a leaner schema.
- Latest-mode RSS `category` carried a single value on both sampled items;
  multi-category comma-joining (seen on some sibling sites) was not
  observed but would pass through unchanged if it occurred.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Telangana Today redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
