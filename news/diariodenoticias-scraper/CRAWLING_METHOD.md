# Crawling Method — Diário de Notícias

**Last verified:** 2026-08-26

## robots.txt

Re-fetched fresh (not reused from an earlier check) as the mandatory first
step:

```
User-agent: *
Sitemap: https://www.dn.pt/sitemap.xml
Sitemap: https://www.dn.pt/news_sitemap.xml
Allow: /
```

**Only one `User-agent` group exists** (`*`), so the "last `User-agent`
line before a shared `Disallow`" parser bug flagged in the research doc
(the "Babak 14" postmortem) cannot apply here -- there's nothing to
misattribute a shared block to. There is no `Disallow` line at all, for
any path. No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` token appears anywhere in the file.
Fully open.

## WAF

`dn.pt` shows **no active challenge of any kind**. The full portfolio
profile ladder was run against the homepage on the same IP:

| Profile | Result |
| --- | --- |
| `chrome124` | 200, 1,483,367 bytes |
| `chrome116` | 200, 1,483,367 bytes |
| `chrome99_android` | 200, 1,483,367 bytes |
| `safari17_0` | 200, 1,483,367 bytes |
| `edge101` | 200, 1,483,367 bytes |

Identical byte-for-byte response on every profile, **zero cookies set** on
any request, no `cf-ray`, no `_abck`/`bm_sz`, no `_px3`/`_pxhd`, no
`x-datadome-cid`, no `x-kasada-tier`. Headers show `x-powered-by: Express`
and a `cache-control` with `s-maxage=10800` (a Node/Express-fronted CDN
cache layer, not a bot-management product). Article pages and the RSS feed
behave identically. **TLS profile pinned:** `chrome124`, consistent with
the portfolio-wide default -- picked from the ladder, not because any
other profile failed.

## CMS identification

dn.pt runs on **Quintype**, a SaaS news-publishing platform (used by many
international outlets). Confirmed via:
- `window.qtVersion` global on every page.
- An embedded `<script id="static-page">` JSON blob with a top-level `qt`
  key (`qt.config`, `qt.data.collection`/`qt.data.story`, `qt.isBotRequest`).
- Story objects carry Quintype-signature fields: `story-content-id`,
  `collection`, `access` / `access-level-value`, `hero-image-s3-key`.
- Media CDN domain `media.assettype.com` / `images.assettype.com`
  (assettype.com is Quintype's own media-CDN brand).

This did not change the extraction approach (JSON-LD is still the primary
source, per portfolio priority order), but explains several field shapes
below and confirms `isBotRequest` is a real server-side signal Quintype
sites can act on (observed `false` for our own unauthenticated `curl_cffi`
requests -- no bot-specific content variant was detected being served to
us).

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.dn.pt/<section>/<slug>` where `<section>` is one of
`sociedade`, `cultura`, `internacional`, `desporto`, `opiniao-dn`,
`opiniao-dn/sociedade-aberta`, etc. Unlike ghanaweb-scraper's single
`@graph` array, dn.pt emits **five separate top-level**
`<script type="application/ld+json">` tags per article page
(`BreadcrumbList`, `WebPage`, `SiteNavigationElement`, `Person`,
`NewsArticle`) -- the extractor scans all ld+json tags and keeps the one
whose `@type` is `NewsArticle`.

The `NewsArticle` node carries a genuinely complete `articleBody` (full
plain text, not a teaser -- confirmed on both free and paywalled samples,
see Paywall section), `headline`, `alternativeHeadline` (always empty on
sampled pieces), `description`, `keywords` (a **comma-separated string**,
not an array -- e.g. `"Dolly Parton,morte,cantora country,obituário,..."`),
`articleSection` (clean category string, e.g. `"Sociedade"`, `"Cultura"`,
`"Opinião DN"`), `datePublished`/`dateModified`/`dateCreated` (ISO-8601
with `+01:00` timezone offset), `inLanguage` (`"pt"`), `thumbnailUrl`,
`mainEntityOfPage`, and `publisher` (a full `NewsMediaOrganization` object
with `sameAs` social links).

Two field shapes differ from ghanaweb's template and are worth flagging
for consumers:
- `author` is always an **array** of `Person` objects (even for a single
  byline), each carrying `name`/`givenName`/`url` (author profile page)
  and sometimes `image`.
- `image` is always an **array** of 3 `ImageObject` crop variants (16:9,
  4:3, 1:1 aspect ratios via `assettype.com`'s on-the-fly image resizing
  query params), not a single object.

### Paywall — SOFT, confirmed with direct evidence

dn.pt runs a **metered/client-side paywall**, not a hard one. Evidence
chain:

1. **HTML/CSS confirms a metering product exists**: the page embeds a full
   `meteredPaywallConfig` JS config block (Portuguese + English copy for
   "3 free premium articles", "Torne-se assinante" / "Sign up to gain
   access to this premium story", a `.paywall-story-styles-m__...` CSS
   module family, and a `key`-icon `premiumStoryIcon` config) -- this is a
   real product, not decorative.
2. **The Quintype embedded state blob exposes a per-article `access`
   field** (`qt.data.story.access` on an article page, or
   `qt.data.collection.items[].story.access` on the homepage feed) with
   observed values `"public"`, `"subscription"`, and `null` (untagged/
   default, treated as free). One homepage item, "940 mil teleconsultas no
   ano passado...", was tagged `access: "subscription"`.
3. **The ld+json `NewsArticle` node mirrors this via the standard
   schema.org soft-paywall pattern**: premium articles carry
   `"isAccessibleForFree": false` plus a `"hasPart": [{"@type":
   "WebPageElement", "isAccessibleForFree": false, "cssSelector":
   ".paywall"}]` entry. Free articles omit `isAccessibleForFree` entirely
   (absent, not `true`).
4. **Critically, `articleBody` is the SAME full, untruncated text on both
   tiers.** Fetched the `access:"subscription"` article
   (`.../940-mil-teleconsultas-...`) with a plain unauthenticated
   `curl_cffi` request -- `articleBody` came back **6,983 characters**,
   a complete multi-section piece with quoted interview material from two
   named sources, not a teaser. Cross-checked independently against the
   same article's `/stories.rss` `<content:encoded>` -- consistent full
   length. A free-tier article
   (`.../morreu-aos-80-anos-a-cantora-country-dolly-parton`, no
   `isAccessibleForFree` key) came back 3,628 characters, also complete.

**Verdict: SOFT paywall.** The paywall is a client-side JS overlay layered
on top of already-fully-rendered SSR HTML/ld+json -- the same family as
`bild-scraper`/`latimes-scraper`. This actor surfaces the signal as a
derived `_paywalled` boolean (`true` when `isAccessibleForFree is False`
or a `.paywall` `hasPart` marker is present) so downstream consumers can
filter/flag premium content, but does not withhold `articleBody` on either
tier -- doing so would throw away data the site itself already delivers.

### 2. Latest headlines — `S2-rss`

`GET https://www.dn.pt/stories.rss`

Not advertised in `robots.txt` (only the two `Sitemap:` lines are) --
found via the `/feed` path, which redirects (302) to `/stories.rss`.
Standard RSS 2.0 with `atom:`/`media:`/`content:` namespace extensions.
Each `<item>` carries `title`, `link`, `guid` (dn.pt's internal story
UUID), `pubDate` (RFC 822), `atom:author` (`atom:name` + `atom:uri` to the
author's profile page), `description` (empty string on all samples
checked -- not populated), `media:keywords` (comma-separated, matches
ld+json's `keywords` shape), one or more `<category>` tags, and
**`content:encoded`** -- which already carries the (near-)full article
body as HTML.

Verified `content:encoded` completeness directly: for
"Portugal pode ajudar a trazer a ONU de 1945 para 2026", the RSS
`content:encoded` plain-text length (6,549 chars after HTML-tag stripping)
closely matched the same article's ld+json `articleBody` length (6,564
chars) -- the ~0.2% difference is whitespace/paragraph-join formatting,
not missing content. This means `fetch_latest` can return full article
text without a second per-item HTTP request.

Only ~17 items were present in one fetch with no offset/paging parameter
found; feed skewed toward the Opinion section (`opiniao-dn`) at the time
sampled, but the freshest item was ~25 minutes old at fetch time --
functionally near-real-time. `section` is derived from the URL path
segment right after `dn.pt/` (e.g. `sociedade`, `cultura`, `opiniao-dn`)
since the feed carries no explicit section field.

**Alternative not used:** `news_sitemap.xml` (Google News sitemap,
advertised in `robots.txt`) was also probed and works (near-real-time,
`news:title`/`news:publication_date`/`news:keywords` shape) but only
carries headline-level metadata, no body text -- RSS was the stronger pick
since it embeds the body for free. `sitemap.xml` itself is a sitemap
*index* (daily-dated child sitemaps going back weeks) -- a viable deep-
crawl/backfill source if ever needed, not used by `latest` mode.

### 3. Not-found behavior

A synthetic bad slug
(`https://www.dn.pt/sociedade/this-is-a-totally-fake-nonexistent-article-slug-xyz123`)
returns a **real HTTP 404** with a small, genuinely distinct placeholder
page (`<title>Ups. Essa página não existe.</title>`, `<meta
name="description" content="A página que tentou aceder não existe...">`,
and a single-node `BreadcrumbList` ld+json with just a "Home" entry, no
`NewsArticle` node) -- not a soft-404 (no HTTP 200 with a fake article
shape). Clean and unambiguous: `not_found` is derived directly from the
status code.

## Known limits

- Only 2 articles sampled in full extraction depth (one `Sociedade` piece
  tagged `access:"subscription"`, one `Cultura` obituary tagged free) plus
  3 more spot-checked for ld+json shape only (`internacional`, `desporto`,
  `opiniao-dn`). A structurally different template (live-blog, photo
  gallery, video feature, the daily e-edition `/edicao-diaria/...`) was
  not sampled and might not carry a `NewsArticle` ld+json node at all.
- `/stories.rss` returned the same ~17 items across repeated fetches in
  the same short window with no visible paging/offset query parameter --
  `limit` values above ~17 will silently return fewer items than
  requested rather than erroring (the actor simply slices `[:limit]`).
  `news_sitemap.xml` (documented above, not wired into `fetch_latest`)
  would be the fallback if a larger single-fetch window is ever needed.
- The `_paywalled` derivation relies on the ld+json
  `isAccessibleForFree`/`hasPart` markers rather than the richer
  Quintype-native `access` field (`public`/`subscription`) seen in the
  embedded `qt` state blob, to keep the extractor on the portfolio's
  JSON-LD-first priority order and avoid depending on an undocumented
  internal CMS state shape. If dn.pt ever stops emitting the ld+json
  markers on premium content while still using `access:"subscription"`
  internally, `_paywalled` would silently read `false` on newly-premium
  articles -- a soft degradation (the text itself still comes through
  fine), not a crash.
- No RSS `description` content was observed on any sampled item (always
  an empty string) -- `description` is populated from ld+json in article
  mode but will typically be `null` in latest mode.

## Diff cadence

Quarterly smoke test recommended.
