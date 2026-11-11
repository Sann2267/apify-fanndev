# Crawling Method — Times of Zambia

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh as the first action of this build (not just re-used from the earlier check the user
had already done). `https://www.times.co.zm/robots.txt` 301-redirects to `https://times.co.zm/robots.txt`
(canonical non-`www` host, matching every other URL on the site). Full body, 115 bytes:

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://times.co.zm/sitemap_index.xml
```

**There is exactly ONE `User-agent` group in the entire file.** This rules out the "Babak 14"
parser-bug pattern flagged in `ACTOR_MARKET_RESEARCHER_NEW.md` (that bug only bites when several
`User-agent` groups share one `Disallow` block and a script checks only the last group before the
block — there is nothing to merge here, since there is only one group, period). No `Claude`,
`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token appears
anywhere in the file. `/wp-json/` (the REST API this actor relies on) and `/feed/` (RSS) are not
disallowed.

## WAF

**No WAF, no challenge, no bot-manager cookie of any kind.** The full profile ladder
(`chrome124`/`chrome99_android`/`safari17_0`/`edge101`/`firefox133`, `curl_cffi`) was run against the
homepage and every single profile returned an identical `200` / `140534` bytes, with **zero cookies
set** in any response. The site is a plain `nginx` reverse proxy in front of PHP (`X-Httpd-Modphp: 1`,
`X-Proxy-Cache`) — no Cloudflare `cf-ray`, no Akamai `_abck`/`bm_sz`, no DataDome/PerimeterX markers,
nothing. This matches the task brief's expectation of a small, modestly-resourced state-owned press
site with no anti-bot investment.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default (no profile-specific
requirement found — any profile in the ladder works equally).

## CMS

WordPress 7.1 (`<meta name="generator" content="WordPress 7.1" />`), a custom theme called
`lian-news`, Rank Math SEO plugin (ld+json + sitemap generation), Google Site Kit (Analytics/gtag).
Standard `wp-json` REST API is live and unauthenticated.

## Data sources

### 1. Article pages — `S1-wpapi` (primary)

`GET https://times.co.zm/wp-json/wp/v2/posts?slug=<slug>&_embed=1`

The article URL's trailing path segment (`https://times.co.zm/<slug>/`) is used directly as the WP
REST API `slug` query filter — no need to fetch the HTML page at all for the common case. `_embed=1`
inlines:
- **`content.rendered`** — the full article body as WordPress block HTML. This is the primary reason
  the REST API is preferred over ld+json/HTML scraping: **the site's `NewsArticle` ld+json block does
  not carry `articleBody` at all** (see S2 below), so without the API a full HTML-scrape fallback
  would always be needed.
- **`_embedded.author[0].name`** — the REAL per-article author name (e.g. `"Shamaoma Musonda"`,
  `"Kali Muluzi"`). This is a second reason to prefer the API: the ld+json `author` field on this site
  is *always* the generic `{"@type": "Organization", "name": "TIMES OF ZAMBIA"}` — never an individual
  — so the API is the *only* source of real bylines found during recon.
- `_embedded.wp:featuredmedia[0]` — lead image with `source_url`/`media_details.width`/`height`.
- `_embedded.wp:term` — two groups, `category` and `post_tag` term objects (name strings extracted).

A slug with no matching post returns `HTTP 200` with an **empty JSON array `[]`** — not a 404 — so
`_try_wpapi` treats an empty list as authoritative `not_found` (verified against a synthetic
`this-article-does-not-exist-zzz123` slug: real page load is a genuine `HTTP 404`, but the API itself
answers `200 []`, both are mapped to `_error: "not_found"`).

**Key quirk — paragraph-class inconsistency:** `content.rendered` markup is NOT uniform across posts.
Some carry the standard Gutenberg `<p class="wp-block-paragraph">`; others (visibly written or
pasted from an LLM chat interface — the class literally reads `<p class="ds-markdown-paragraph">`,
i.e. a DeepSeek-style markdown-to-HTML converter's output class, still present verbatim in the
published HTML) use a different class entirely. The extractor collects **every** `<p>` tag inside
`content.rendered` unconditionally rather than filtering by class, so both variants parse correctly.
This is worth flagging for anyone consuming this actor's output: at least part of this outlet's
content appears to be LLM-assisted or LLM-authored, based on residual markup fingerprints — the
prose itself reads as ordinary news copy with no other obvious tells.

**Key quirk — "Video"-category posts have empty bodies:** posts whose slug is prefixed `watch-`
(category `"Video"`) carry `content.rendered` that is empty or a single empty `<p>` tag — the real
content is a lazy-loaded YouTube-style embed (`smush-lazyload-video` div + iframe), which carries no
text at all. Confirmed on `watch-inside-zescos-kariba-control-room-during-peak-load-shedding`
(`articleBody: null` in the captured sample below). This is genuine site shape, not a parse failure —
the extractor does **not** raise `UnexpectedShape` for an empty body; `excerpt.rendered` still carries
a usable one-paragraph summary for these posts. `"photo-focus-"`-prefixed posts (photo galleries) were
not sampled in depth but are expected to behave similarly (image-driven, thin/no body text).

### 2. Article pages — `S2-jsonld+html` (fallback, used only if S1 fails)

If the WP REST API call itself errors out after retries (non-200, timeout, malformed JSON), the
actor falls back to fetching the article's HTML page directly and reading:
- The standalone `<script type="application/ld+json">` block with `"@type": "NewsArticle"` —
  `headline`, `datePublished`, `dateModified`, `description`, `image` — but note `author` here is
  always the generic `"TIMES OF ZAMBIA"` organization, never an individual (see above).
- `div.entry-content` (class confirmed via `<div class="entry-content lian-article-content">` on the
  rendered page) for the body text, collecting all `<p>` tags the same way as S1.

This path was verified to work correctly end-to-end (same output shape as S1, minus the WP-API-only
fields like `id`/`categories`/`tags`/real author), but was never actually exercised during testing
since the REST API was reachable on every sampled article — it exists purely as the defense-in-depth
fallback the portfolio convention calls for.

### 3. Latest headlines — `S3-rss`

`GET https://times.co.zm/feed/` (page 1), `https://times.co.zm/feed/?paged=N` for subsequent pages.
Standard WordPress default feed, 10 items per page. Confirmed pagination works cleanly up to at least
5 pages of real content; requesting a page past the end (`?paged=100`) returns a clean `HTTP 404` with
zero items — treated as "stop paginating, return what we have" rather than an error, since page 1
already succeeded. `limit` is capped at 50 (5 pages) by the input schema, well within the confirmed
range.

Feed fields captured: `title`, `link`, `dc:creator` (real author name, matches WP-API author),
`pubDate` (RFC 822), `description` (short summary), `content:encoded` (full body HTML — same
paragraph-class caveat as S1 applies, parsed the same way), and the full `category` list (WordPress's
feed conflates categories and tags into one repeated `<category>` element per item, unlike the WP REST
API which separates them — passed through as a single flat `categories` list here since the feed
itself gives no way to tell them apart).

`sitemap_index.xml` (advertised in `robots.txt`) was also checked — it's a standard Rank Math
sitemap index (`post-sitemap.xml`, `page-sitemap.xml`, `category-sitemap.xml`) with no per-item
metadata beyond `loc`/`lastmod`, strictly worse than the RSS feed for `latest` mode. Not used.

## Paywall behavior

**None found.** `content.protected` (WordPress's own field for password-protected/paywalled content)
was `false` on every sampled article. No `isAccessibleForFree` field appears anywhere (ld+json doesn't
carry it on this site at all). No "subscribe"/"premium"/"member-only" marker in any article body. The
`/subscribe/` and `/e-paper/` links visible in the site nav lead to the print e-paper (PDF edition)
subscription product, unrelated to web article access — every web article sampled (including ones
published the same day as the recon date) returned full, unrestricted `articleBody` text.

## Known limits

- The WP REST API is the far richer, far more reliable data source on this site (real author names,
  full body, structured categories/tags) — `S2-jsonld+html` exists for defense-in-depth but was never
  actually triggered during recon/testing (every sampled slug resolved via the API). If the site ever
  locks down `/wp-json/` (as `nypost-scraper` found on its own target — see that actor's
  `constants.py`), S2 becomes the only path and author attribution degrades to the generic
  `"TIMES OF ZAMBIA"` organization string.
- `articleBody` can be `null`/empty for "Video"-category (`watch-`-prefixed slug) posts and possibly
  photo-gallery posts — this is real site content shape (video-embed articles have no text body), not
  a bug. Consumers wanting a fallback summary for these should use `description`, which is still
  populated.
- Only ~7 articles sampled in depth (news, sport, business, entertainment/feature, one video-format
  post). A live-blog or interactive-format template, if this site has one, was not sampled.
- `date`/`date_gmt`/`modified`/`modified_gmt` on S1 are passed through exactly as WordPress emits them
  — `date`/`modified` have no timezone suffix but are in the site's local time (Africa/Lusaka, UTC+2,
  confirmed by comparing to the `_gmt` twin fields, which are consistently 2 hours behind). Don't
  assume `date` is UTC.
- RSS `categories` mixes WordPress categories and tags into one flat list (feed limitation, not an
  actor bug) — use the WP-API path's separate `categories`/`tags` fields if you need them
  disambiguated.

## Diff cadence

Quarterly smoke test recommended.
