# Crawling Method — The Statesman (India)

**Last verified:** 2026-08-27

The Statesman (`thestatesman.com`) is a national English-language Indian
daily newspaper headquartered in New Delhi (est. 1875).

## Robots.txt

```
User-agent: *
Disallow: /wp-admin/
Disallow: /test
Allow: /wp-admin/admin-ajax.php

Sitemap: https://www.thestatesman.com/googlenews.xml
Sitemap: https://www.thestatesman.com/sitemap.xml
Sitemap: https://www.thestatesman.com/webstories.xml
```

Only one `User-agent: *` group, disallowing just `/wp-admin/` and `/test`
(standard WordPress hygiene). No `Claude`/`ClaudeBot`/`Claude-Web`/
`Claude-User`/`Claude-SearchBot`/`anthropic-ai` user-agent group of any
kind, and no natural-language prohibition against AI/LLM crawling anywhere
in the file. Independently re-verified with a fresh `curl` fetch during
this build (`GET https://www.thestatesman.com/robots.txt` -> HTTP 200,
body as above) — confirmed crawlable. This re-verifies (and confirms) the
prior screening note from Babak 18/19 of `ACTOR_MARKET_RESEARCHER_NEW.md`.

## WAF

**Cloudflare is present**, but a `curl_cffi` `chrome124` impersonated
request clears it on the first try, every time — homepage, article pages,
and both sitemaps all returned a clean 200 during recon, `server:
cloudflare` header present but no `Just a moment...` interstitial body.

A **plain, non-impersonated** `requests` call to the exact same homepage
URL got a genuine Cloudflare JS-challenge: HTTP 403, `<title>Just a
moment...</title>`, a `challenges.cloudflare.com` CSP directive. This
confirms the WAF is live and that TLS-fingerprint impersonation alone
(no cookie harvesting, no JS-challenge solving, no browser) is what clears
it — matching the portfolio's HTTP-only-first doctrine.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

`/feed` and `/rss` both return an HTTP 500 WordPress `wp_die` error body
(`"No feed available, please visit the homepage"`) — no RSS feed is
exposed on this site. `latest` mode uses `/googlenews.xml` instead.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.thestatesman.com/<section>[/<subsection>]/<slug>-<numeric-id>.html`

Each article page emits **6** separate `<script type="application/ld+json">`
blocks:

1. An `@graph`-wrapped block containing `Article` + `WebPage` nodes. The
   `Article` node here carries `headline`, `author` (name + `@id` only, no
   URL), `datePublished`, `wordCount`, `commentCount`, `keywords` (real
   array of topic tags), `thumbnailUrl` — but **no `articleBody`**.
2. A `BreadcrumbList` block.
3. A **standalone, bare** (not `@graph`-wrapped) block with
   `"@type": "newsarticle"` — **lowercase**, non-standard casing, unlike
   the `"NewsArticle"` (PascalCase) seen elsewhere in this portfolio. This
   is the block actually consumed: it carries the full plain-text
   `articleBody` (confirmed non-empty on every sampled article, 2,100–
   8,100+ characters), plus `headline`, `description`, `datePublished`,
   `dateModified`, `author` (full `Person` dict with `name` **and** `url`),
   `image` (full `ImageObject` dict with `url`/`width`/`height`),
   `publisher` (`Organization`), `articleSection`, `mainEntityOfPage`,
   `inLanguage`. **It never carries `keywords`, `wordCount`, or
   `commentCount`** on any sampled article.
4. A `NewsMediaOrganization` block (site-wide, not article-specific).
5. A `SiteNavigationElement` block (site-wide nav links).
6. A `WebSite` block.

**Quirk — split article data across two blocks:** the fields a scraper
actually wants (`articleBody`, full `author.url`, full `image` dims) live
only on block 3 (the `newsarticle` block), while `keywords`/`wordCount`/
`commentCount` live only on block 1's `@graph` `Article` node.
`extract_article()` treats block 3 as primary and merges `keywords`/
`wordCount`/`commentCount` in from block 1's `Article` node when present,
without overwriting anything already on the primary block.

**Quirk — generic byline:** every one of 6 sampled articles across 5
different sections (India, Cities/Kolkata, Sports, Entertainment/Bollywood)
carried the exact same generic newsroom byline —
`{"@type": "Person", "name": "Statesman News Service", "url":
"https://www.thestatesman.com/author/authorthestatesman-com"}` — never a
named reporter. Passed through as-is per raw-passthrough convention; not
normalized or dropped.

**Quirk — soft-404 (no real 404 for bad slugs):** a deliberately-invented
nonexistent slug
(`/sports/some-invented-nonexistent-slug-1234567890.html`) did **not**
return HTTP 404. WordPress instead issued a real `302` redirect (confirmed
with `allow_redirects=False`) to the parent category listing page
(`/sports`), which itself returns a clean `200` with valid — but
different-shaped — `BreadcrumbList`/nav JSON-LD and no `newsarticle` block
at all. Detected in `main.py`'s `_looks_like_article_url()` by checking
whether the *final* URL (after redirects) still ends in
`-<numeric-id>.html`; every real sampled article URL does, category/listing
pages never do. This turns the soft-404 into a clean `_error: "not_found"`
row instead of a generic `UnexpectedShape` crash.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.thestatesman.com/googlenews.xml`

Since no RSS feed is exposed (see WAF section), `latest` mode reads the
Google News sitemap referenced from `robots.txt` instead — confirmed live
with **342** `<url>` entries, each carrying `<loc>`, `<news:title>`,
`<news:publication_date>` (real per-article ISO 8601 timestamp with
`+05:30` IST offset), and `<news:keywords>` (comma-separated string,
split into an array). Confirmed newest-first in file order during recon
(five consecutive sampled entries in strictly descending
`publication_date`, spanning a ~20-minute same-morning window) —
`extract_sitemap_items()` sorts descending by `publicationDate`
defensively anyway, matching portfolio convention.

`robots.txt` also references `/sitemap.xml` (a standard Yoast sitemap
index, 133 KB — not directly usable for "latest" without walking child
sitemaps) — `/googlenews.xml` was chosen since it's already a tight,
purpose-built recency feed with real publish timestamps and no extra
indirection.

## Paywall behavior

No `isAccessibleForFree` (or equivalent) metering flag was found on any
sampled `newsarticle` JSON-LD block — the field is simply absent, not
`false`. No truncated `articleBody`, no "subscribe to continue reading"
marker, no login wall found on any of the 6 sampled articles across 5
sections. The Statesman's news content does not appear to be paywalled.

## Known limits

- Soft-404 detection relies on the `-<numeric-id>.html` URL-suffix
  heuristic holding across the whole site; if The Statesman ever ships a
  URL scheme without that suffix for some content type, those pages would
  incorrectly get flagged `not_found`. Not observed during recon (article
  URLs sampled from 5 different sections all matched).
- 6 articles sampled in depth (India ×3, Cities/Kolkata, Sports, Bollywood)
  plus one invented-slug redirect probe. A structurally different template
  (e.g. opinion/editorial, live cricket score widget, photo gallery, or
  web story) was not sampled.
- `/sitemap.xml`'s child sitemaps (a larger rolling archive) exist as an
  alternate "latest" source but aren't wired up — `/googlenews.xml`'s
  342-entry recency window was judged sufficient and needs no extra
  indirection.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the standalone `newsarticle` ld+json block still
carries `articleBody`. If The Statesman redesigns the page,
`extract_article` will raise `UnexpectedShape` and the run will fail
loudly rather than emit corrupt records.
