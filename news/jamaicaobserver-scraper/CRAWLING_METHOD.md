# Crawling Method — Jamaica Observer

**Last verified:** 2026-08-26

The Jamaica Observer (`jamaicaobserver.com`) is one of Jamaica's two main
daily newspapers. It is **not related to The Gleaner**
(`jamaica-gleaner.com`, already covered by this portfolio's
`jamaicagleaner-scraper`) — the two are direct competitors, separate
publishers, separate owners.

## Robots.txt

```
User-agent: *
Disallow: 
Allow: /
Sitemap: https://www.jamaicaobserver.com/sitemap.xml
User-agent: grapeshot 
Disallow: 
```

121-byte file, two `User-agent` groups, both with an empty `Disallow:`
(allow-all). No Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai
disallow anywhere, and no plain-English natural-language prohibition against
AI/LLM training or scraping in any comment (there are no comments at all).
Independently re-verified with a fresh `curl_cffi` `chrome124` fetch during
this build (`GET https://www.jamaicaobserver.com/robots.txt` -> HTTP 200,
body as above) — confirmed crawlable.

## WAF

**None found.** Even a plain `requests` baseline with no TLS impersonation
gets a clean HTTP 200 on the homepage (`server: BunnyCDN-LA1-900` — a CDN,
not a WAF product). `curl_cffi chrome124` is used anyway for consistency
with the portfolio-wide default and as a hedge against a future WAF rollout.

**TLS profile pinned:** `chrome124`.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.jamaicaobserver.com/YYYY/MM/DD/<slug>/`

The page emits three `<script type="application/ld+json">` blocks:
`NewsMediaOrganization` (site-wide, not article-specific), `NewsArticle`
(`headline`, `datePublished`, `dateModified`, `image`, `isAccessibleForFree`,
`articleSection`), and `BreadcrumbList`. **No `articleBody` and no
`author`** in the ld+json.

`articleSection` sometimes carries a literal double-HTML-escaped `&amp;`
(e.g. `"Art &amp; Culture"` on the Celene Hall / Miss Universe Jamaica
article) — `html.unescape()` is applied to every text value pulled from the
graph.

Full body text comes from `div.content-single-wrap` — confirmed a **unique**
selector on the page (exactly 1 match), unlike the bare `body` class it also
carries (9 unrelated matches elsewhere on the page). Direct-child `<p>` tags
only (`recursive=False`) — confirmed clean across 3 sampled articles (22
paragraphs on one sample), no ad/related-article junk mixed in even though
non-`<p>` sibling `<div>` elements (inline images, embeds) are interleaved
between paragraphs at the same nesting level.

**No author byline found anywhere in HTML** on any sampled article — no
meta tag (`article:author` absent), no visible byline element (a
`.date_with_author`/`.author_image` CSS rule exists in the theme's
stylesheet, but the corresponding HTML element is never rendered on any
sampled page — dead theme CSS). The WordPress REST API
(`/wp-json/wp/v2/posts?slug=<slug>`) resolves `author` to user id `1`,
which is a generic **"tecnavia"** import/syndication account (a print
e-edition publishing pipeline vendor — its `guid`/RSS-item `<guid>` values
also point at `*.newsmemory.com`, tecnavia's hosted platform), not the real
reporter — so the REST API was **not** used as an author source either.
`author` is intentionally omitted from article-mode output rather than
fabricated. The real reporter byline (name + title + email, e.g. `"Arthur
Hall Editor HallA@jamaicaobserver.com"`) is only available via `latest`
mode's RSS `dc:creator` field — not reachable when starting from a bare
article URL.

A terminal/console display artifact was investigated and ruled out as a
real data quirk: printing article body text to a Windows PowerShell/cmd
console can show `�` in place of curly quotes/apostrophes, but the actual
JSON/HTML bytes are correct valid UTF-8 (confirmed: raw bytes contain the
proper `’` JSON escape / UTF-8 encoding of U+2019, and
`json.loads` decodes it to the correct codepoint — only the terminal's own
codepage fails to render the glyph). No unescaping or cleanup was needed
for this.

### 2. Latest headlines — `S2-rss`

`GET https://www.jamaicaobserver.com/feed/`

Standard WordPress RSS 2.0 feed, confirmed working cleanly (37 items per
fetch) — unlike jamaicagleaner-scraper's sibling site, where both
`sitemap.xml` (404) and `rss.xml` (empty stub) are broken and a
homepage-link-scrape fallback was required. No fallback was needed here.

Each `<item>` carries `title`, `link` (the real public article URL),
`guid` (an internal `*.newsmemory.com` URL — NOT the public URL, use `link`
instead), `pubDate` (RFC 822), `dc:creator` (a genuine reporter byline
string, not a Cloudflare-obfuscation placeholder), `category`, and full
`content:encoded` (the complete article body as HTML, including the lead
paragraph in `<b>` tags) — richer than what's reachable from the bare
article URL alone (see author note above).

### 3. WordPress REST API — investigated, not used

`GET /wp-json/wp/v2/posts?slug=<slug>` returns HTTP 200 with clean rendered
`content.rendered` HTML (would be a viable primary content source), but
`author` resolves to the generic "tecnavia" pipeline account (see above), so
it offers no advantage over the ld+json + HTML-body approach actually used
and was dropped to keep article-mode to a single HTTP request. A missing
slug returns HTTP 200 with an empty JSON array `[]`, not a 404 — noted here
in case a future revision of this actor adds REST API as a fallback
strategy (would need explicit empty-array handling, unlike the real 404 the
HTML page itself returns for a nonexistent slug).

## Paywall behavior

None observed as a hard gate. `isAccessibleForFree: true` on all 3 sampled
articles (News x2, Art & Culture/Entertainment).

## Known limits

- `author` is unavailable in `article` mode (see above) — only present in
  `latest` mode as the RSS `creator` field.
- Only 3 articles sampled in depth (News x2, Art & Culture/Entertainment). A
  structurally different template (live-blog, photo gallery, video,
  opinion/column) was not sampled and might lack `div.content-single-wrap`
  entirely — would raise `UnexpectedShape` rather than silently emit a
  wrong or empty record.
- RSS `guid` is an internal `newsmemory.com` URL, not a public link — `link`
  is the field to use.

## Diff cadence

Quarterly smoke test recommended.
