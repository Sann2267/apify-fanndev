# Crawling Method — Zambia Daily Mail

**Last verified:** 2026-08-26

## robots.txt

Re-fetched fresh, independently of the orchestrator's earlier fast screen, as the first action of
this build. `https://daily-mail.co.zm/robots.txt` 301-redirects to
`https://www.daily-mail.co.zm/robots.txt` (canonical `www` host — the reverse of Times of Zambia,
which canonicalizes to non-`www`; the redirect itself is issued by WordPress, `X-Redirect-By:
WordPress`). Full body:

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://www.daily-mail.co.zm/wp-sitemap.xml
```

**There is exactly ONE `User-agent` group in the entire file.** No Babak-14 merged-Disallow-block
risk (that bug only bites when several `User-agent` groups share one `Disallow` block). No `Claude`,
`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token appears
anywhere in the file. `/wp-json/` (this actor's data source) is not disallowed.

## WAF

**No WAF, no challenge, no bot-manager cookie of any kind.** `curl_cffi chrome124` gets a clean `200`
with **zero cookies set** on the homepage, article pages, and the WordPress REST API. Plain `nginx`
reverse proxy in front of PHP (`Server: nginx/1.18.0 (Ubuntu)`) — no Cloudflare `cf-ray`, no Akamai
`_abck`/`bm_sz`, no DataDome/PerimeterX markers. Matches the task brief's expectation of a small,
modestly-resourced state-owned press site with no anti-bot investment — same posture as
`timesofzambia-scraper`.

**TLS profile pinned:** `chrome124`, portfolio-wide default.

## CMS

WordPress 6.3.2, **OceanWP** theme for archive/listing templates, **Elementor 3.17.2 + Elementor
Pro** for individual post templates (each article is built as an Elementor "Single Post" template,
not the theme's default post template — this explains why article pages and category-archive pages
have completely different HTML structures, see below). One stray asset URL
(`https://daily.apexinventionszambia.com/wp-content/plugins/elementor/...css`) leaks the web
developer's staging domain — cosmetic only, does not affect scraping.

**No SEO plugin active.** Unlike most WordPress sites in this portfolio, article pages carry **no
`ld+json` `NewsArticle` block and no Open Graph meta tags at all** (confirmed absent by regex/scan on
multiple sampled articles) — no Yoast, no Rank Math. This rules out the usual "prefer ld+json"
extraction tier entirely; the WordPress REST API and raw HTML are the only two options.

## Critical quirk — REST API collection endpoints silently ignore all query strings

This is the load-bearing finding of this recon and the reason the article-mode strategy differs from
every other WordPress actor in this portfolio (including `timesofzambia-scraper`, which uses
`?slug=...&_embed=1` successfully).

Tested directly:
```
GET /wp-json/wp/v2/posts?slug=this-article-does-not-exist-zzz123   -> 200, same 10 items as unfiltered
GET /wp-json/wp/v2/posts?slug=totally-bogus-999                     -> 200, same 10 items
GET /wp-json/wp/v2/posts?slug=no-tolerance-for-anarchy-hh (real)    -> 200, same 10 items
GET /wp-json/wp/v2/posts?search=no-tolerance-for-anarchy            -> 200, same 10 items
GET /wp-json/wp/v2/posts?categories=3                                -> 200, same 10 items (mixed cats)
GET /wp-json/wp/v2/posts?per_page=3                                  -> 200, 10 items (not 3)
GET /wp-json/wp/v2/posts?page=2                                      -> 200, identical to page 1
```
Every response carries `X-WP-Total: 1478` / `X-WP-Totalpages: 148` — the whole site's post count —
confirming the filter/pagination is never applied server-side, not merely cached identically. Root
cause not conclusively identified (candidates: a security/hardening mu-plugin stripping REST query
args, or a LiteSpeed Cache misconfiguration caching the collection endpoint by path only — the site
does run LiteSpeed, `X-Litespeed-Tag` header present on every response). The default WordPress feed
suffers the identical symptom: `/feed/` and `/feed/?paged=2` return byte-identical item lists.
`wp-sitemap.xml` (advertised in robots.txt) is a dead end for an unrelated reason — it 501s with
`Could not generate XML sitemap due to missing SimpleXML extension` (a genuine PHP extension missing
on their server, not a bot block).

**Singular by-ID endpoints are unaffected and work correctly** — confirmed on
`/wp-json/wp/v2/posts/5159`, `/users/2`, `/media/5160`, `/categories/18`, `/categories/2`, each
returning the exact correct single resource.

### Consequence for article mode — S1-wpapi-by-id

Since slug-based lookup is unusable, the actor instead:
1. Fetches the article's own HTML permalink (needed anyway to detect 404).
2. Reads the numeric post ID out of WordPress's standard REST-discovery `<link>` in `<head>`:
   `<link rel="alternate" type="application/json" href="https://www.daily-mail.co.zm/wp-json/wp/v2/posts/5159" />`
   — present on every sampled article, unaffected by the query-string bug since it carries no query
   string itself.
3. Calls that URL directly (`/wp-json/wp/v2/posts/<id>`), which reliably returns the correct post.
4. Resolves `author`/`featured_media`/`categories`/`tags` (all returned as bare numeric IDs — `_embed=1`
   was tried and does **not** work on this site: the `_links` section correctly advertises
   `"embeddable": true` hrefs, but the `_embedded` key never appears in the response body regardless)
   via one follow-up singular-endpoint call each, run concurrently with `asyncio.gather`.

Verified end-to-end against two distinct real articles (ids 5159 and 5153) — both round-trip
correctly through the discovery-link → by-ID lookup path.

**Key quirk — bylines are not structured data.** This install has only two WordPress user accounts
(`webmaster`, `Website Editor`) — every sampled article's `author` field resolves to one of these
generic accounts, never an individual reporter. The real byline (e.g. "MARY LEMBA, Lusaka", "CHOMBA
MUSIKA, Lusaka") is written as plain text into the first paragraph of `content.rendered` itself, same
pattern seen on other African state-press outlets in this portfolio.

**Key quirk — no paywall.** `content.protected` was `false` on every sampled article; no
subscribe/premium markers found anywhere.

### S2-html (fallback, used only if the discovery-link or by-ID API path fails)

Since there's no ld+json/OG on this site, S2 reads the raw Elementor markup directly:
- Headline: `.elementor-widget-theme-post-title .elementor-heading-title` (falls back to `<h1>`).
- Body: `div[data-widget_type^="theme-post-content"] .elementor-widget-container`, collecting all
  `<p>` tags — confirmed present and correctly populated (`<p><strong>MARY LEMBA </strong>...`).
- Date: `.elementor-post-info__item--type-date` ("August 21, 2026") +
  `.elementor-post-info__item--type-time` ("7:57 pm") — no ISO datetime attribute exists anywhere on
  the page, so this is a best-effort text parse (`_parse_local_datetime` in `extractor.py`), verified
  to reproduce the exact same value as S1's `date_gmt` field on the sampled article
  (`2026-08-21T19:57:00` vs `2026-08-21T19:57:04` — matches to the minute, S2 has no seconds
  precision since none is displayed).
- No description/author/categories available on this path (genuine absence, not a parse failure).

This path was verified to work correctly end-to-end (same headline/body/date as S1, minus the
API-only structured fields) but was never actually triggered during normal testing since the by-ID
API path succeeded on every sampled article — it exists purely as the defense-in-depth fallback the
portfolio convention calls for.

**Encoding false-alarm, noted for future agents:** curly quotes (`\xe2\x80\x99` / U+2019) in article
bodies can appear as a literal replacement-character glyph when printed to a Windows console — this
was double-checked with `ord()` on the actual decoded string and confirmed to be a real, correct
U+2019 codepoint every time. It is purely a terminal codepage rendering artifact (this environment's
`cmd`/PowerShell console is not UTF-8 by default), not a decoding bug in `curl_cffi`/BeautifulSoup or
in this site's own encoding. Do not "fix" this by adding manual re-decoding logic — the data is
already correct; only the terminal display is misleading.

### Latest headlines — S3-archive (NOT RSS, NOT the REST collection endpoint)

Both the RSS feed and the REST collection endpoint are stuck on the same static 10 items regardless
of pagination params (see above) — neither is usable for `latest` mode beyond the first 10 items.
Instead, the actor paginates the **"Headlines" category archive page**:

```
GET https://www.daily-mail.co.zm/category/headlines/           (page 1)
GET https://www.daily-mail.co.zm/category/headlines/page/2/    (page 2)
...
```

Category id 18 ("Headlines") is attached to every single sampled post alongside its more specific
section category (News/Business/Sport/Editorial Comment/...) — i.e. it functions as this site's
global "everything" tag, and its archive-page order exactly matches the (static, unpaginatable)
default order of the RSS feed / REST collection endpoint. Unlike the feed/REST endpoints, this
**path-based** pagination is genuinely real: pages 1, 2, and 3 were confirmed to return
zero-overlapping, chronologically-continuing sets of 10 articles each, and an out-of-range page
(`/page/500/`) returns a clean `404` rather than repeating content. This is the theme's (OceanWP)
default blog-listing template, which is a completely different HTML structure from the Elementor
single-post template used by S2 — `<article class="... post-<id> ... hentry ...">` cards, each with
title (`h2.blog-entry-title a`), author (`.meta-author a`), plain-text date (`.meta-date`, no
time-of-day shown), categories (`.meta-cat a`), a short excerpt (`.blog-entry-summary p`), and a
thumbnail (`.thumbnail img`). Does **not** carry full article body — only the article-mode path
(S1-wpapi-by-id / S2-html) returns full text; `latest` mode is headline+summary only by design, to
avoid an extra full fetch per item.

## Known limits

- `latest` mode tops out at whatever the "Headlines" category archive holds — untested beyond ~3
  pages (30 items) during recon, but the input schema caps `limit` at 50 (5 pages), well within the
  same order of magnitude validated for `timesofzambia-scraper`'s RSS pagination and consistent with
  the site's `X-WP-Total: 1478` total post count (plenty of pages exist).
- Author attribution is essentially always the generic "Website Editor" account — see quirk above.
  Real bylines are free text in the article body, not queryable/filterable structured data anywhere
  on this site.
- No `ld+json`/Open Graph on this site at all — a rarity in this portfolio. If Elementor Pro or a
  future SEO plugin is added and starts emitting `NewsArticle` ld+json, S2 should be revisited to
  prefer it over the current CSS-selector-based Elementor scrape.
- The REST collection query-string bug's root cause (security mu-plugin vs. LiteSpeed Cache
  misconfiguration) was not conclusively identified — if it's ever fixed upstream, the
  `?slug=`-based lookup pattern used by `timesofzambia-scraper` would become viable here too and
  could replace the current two-request discovery-link approach, but there's no need to revisit
  proactively since the current approach works reliably.
- Only 2 articles sampled in full depth (both "Headlines"/"News" category, political coverage from
  the week of the 2026 Zambian general election). Sport/Business/Entertainment templates were spot
  checked via the archive listing only, not fetched individually — assumed to share the same
  Elementor single-post template based on consistent site-wide theme usage, not directly confirmed.

## Diff cadence

Quarterly smoke test recommended.
