# Crawling Method — Saudi Gazette

**Last verified:** 2026-08-26

## WAF

`saudigazette.com.sa` shows **no active challenge**. Even a plain `curl`
with a generic Chrome UA (no TLS impersonation at all) got a clean 200 on
the homepage, 3 sampled article pages (news, opinion, wire/tech), the news
sitemap, and a synthetic 404 probe. `curl_cffi` `chrome124` was used for
the actual actor regardless, per portfolio convention. The site sits
behind both Cloudflare and CloudFront (`server: cloudflare`, `cf-ray`, and
`via: 1.1 ...cloudfront.net` headers all present simultaneously) but this
is CDN plumbing only -- no "Just a moment" interstitial, no `cf-mitigated`
header, no 403 anywhere.

`robots.txt` re-verified independently (per project policy after a past
incident where a fast screen missed a block):

```
User-agent: Baiduspider
Disallow: /
User-agent: Baiduspider-video
Disallow: /
User-agent: Baiduspider-image
Disallow: /
User-agent: istellabot
Disallow: /
User-agent: SemrushBot
Disallow: /
User-agent: DotBot
Disallow: /

#User-agent: bingbot
#Disallow: /

User-agent: Twitterbot
Crawl-delay: 25

User-agent: *
Disallow: /*page=
Disallow: /ajax/
Disallow: /search/
Disallow: /digital
Disallow: /*.pdf
Crawl-delay: 10

Sitemap: https://saudigazette.com.sa/sitemaps/sitemap_0.xml
Sitemap: https://saudigazette.com.sa/sitemaps/news_sitemap.xml
```

Each `User-agent` group has its own directly-attached `Disallow` block (no
shared/merged group spanning multiple user-agents -- the "Babak 14"
parser-bug pattern flagged in the project research doc does not apply
here). No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` token appears anywhere in the file,
under any group. The only fully-blocked crawlers are SEO/analytics bots
(Baiduspider variants, istellabot, SemrushBot, DotBot) -- irrelevant here.
The `User-agent: *` group has narrow path disallows only (query-string
pagination, `/ajax/`, `/search/`, `/digital`, PDFs) -- no blanket
`Disallow: /`, and none of it overlaps `/article/<id>/<slug>` or
`/sitemaps/news_sitemap.xml`, the two paths this actor uses.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://saudigazette.com.sa/article/<id>/<category>/<slug>`

Two standalone `application/ld+json` blocks are present: a site-wide
`Organization` block (irrelevant), and a `NewsArticle` block carrying
`headline`, `description`, `datePublished`, `dateModified`, `author`
(`{"@type": "Person", "name": ...}`), `publisher.name`, `image.url`, and
`keywords` -- but **no `articleBody`**.

`author.name` genuinely varies by article type (all 3 confirmed on
sampled articles, not assumed):
- `"Saudi Gazette"` -- staff/generic byline (e.g. the discover-saudi
  archaeology piece)
- `"Agencies"` -- wire copy (e.g. the Trump/China humanoid-robots tech
  piece)
- `"By Abdullah AlFarha AlGhamdi*"` -- opinion columns. The raw
  `"By "`-prefixed, `"*"`-suffixed string is kept verbatim rather than
  cleaned, per the portfolio's minimal-renaming/raw-passthrough
  convention.

`keywords` is sometimes genuinely curated (the archaeology piece:
`"Saudi Arabia, AlUla, Khaybar and Tayma, Royal Commission for AlUla,
ancient, tomb stones, Bronze Age, archeology, "`) and sometimes CMS
auto-generated filler -- the opinion piece's `keywords` is literally its
own headline comma-joined word-by-word
(`"Beyond,the,scoreline:,Why,Saudi,football,needs,a,governance,review"`).
Passed through as-is, not filtered or detected.

**Quirk:** `description` (and occasionally other ld+json text fields)
contains **literal un-decoded HTML entities inline** -- confirmed
`&#039;` in the opinion piece's description (`"...Saudi Arabia&#039;s
World Cup run..."`). This is not a JSON-escaping issue (`json.loads`
already handles real JSON string escapes) -- the CMS embeds actual HTML
entities directly into the text value. A `html.unescape()` pass on
`headline`/`description`/`author.name`/`publisher.name`/`keywords`
cleans this up.

`category` is **not present anywhere in the ld+json** -- pulled instead
from the single active breadcrumb link, `div.breadcrumbs a.breadcrumb`
(observed values: `"discover saudi"`, `"Opinion"`, `"TECHNOLOGY"` --
casing is inconsistent upstream, kept as-is).

Full body text comes from HTML: `div.body-div`, direct-child
`<p>`/`<h2>`/`<h3>`/`<blockquote>` tags only. In-body `<picture>` elements
(inline images) sit inside their own `<p>` wrapper at the same DOM level
and are excluded automatically -- `get_text()` on a picture-only `<p>`
returns an empty string, which is dropped before joining. Confirmed clean
on all 3 sampled articles (archaeology: 1.4 KB / 5 paragraphs, opinion:
10.5 KB, tech/wire: 4.2 KB), no ad/promo/share-widget text leaking in.

No `isAccessibleForFree` field or other paywall marker was found in any
sampled `NewsArticle` node.

### 2. Latest headlines — `S2-sitemap`

`GET https://saudigazette.com.sa/sitemaps/news_sitemap.xml`

Google News sitemap, explicitly advertised via `Sitemap:` in
`robots.txt`. A rolling window of the newest ~80 articles -- the freshest
item on a live fetch was published under 15 minutes before the request.
Standard shape: `loc`, `news:title`, `news:publication_date`,
`news:keywords` (comma-split into a list) per `<url>` entry. No
`image:*` namespace on this feed (confirmed absent -- 0 matches for
`image:loc`/`<image:image>` across the whole document), unlike
gulfnews-scraper's sitemap.

No RSS feed exists:
- `https://saudigazette.com.sa/rss.xml` -- 301-redirects to
  `https://saudigazette.com.sa/404`, which itself returns HTTP 404.
- `https://saudigazette.com.sa/rss` -- soft-200s to an HTML placeholder
  page (`<title>RSS - Latest News from Saudi Arabia and the World</title>`,
  a `<meta http-equiv="refresh" content="300">` auto-refresh tag, but no
  `<rss>`/`<item>` XML anywhere in the body).
- `https://saudigazette.com.sa/feed` -- 301-redirects to `/404` the same
  way `/rss.xml` does.

Both dead ends; `news_sitemap.xml` is the only viable and, being
near-real-time, sufficiently fresh `latest`-mode source.

## Paywall behavior

None observed. Free, ad-supported portal; no "subscribe"/"paywall"/
"premium"/"member-only" marker found in raw HTML on any sampled page, and
no `isAccessibleForFree` flag emitted in ld+json.

## Known limits

- `category` casing is inconsistent upstream (`"discover saudi"` lowercase
  vs `"TECHNOLOGY"` uppercase vs `"Opinion"` title-case) -- passed through
  verbatim, not normalized, per the raw-passthrough convention.
- `keywords` on article-mode records is sometimes genuinely curated tags,
  sometimes the CMS's own headline auto-split into a comma list -- no
  attempt is made to distinguish the two upstream data-quality tiers.
- Only 3 articles sampled in depth (1 discover-saudi/archaeology feature,
  1 opinion column, 1 technology/wire piece), plus the news sitemap and a
  synthetic 404 probe. A structurally different template (live-blog,
  photo gallery, video feature) was not sampled and might not fit the
  `div.body-div` selector.
- Invalid/deleted article IDs 301-redirect to `/404`, which itself is a
  real HTTP 404 (not a soft-404 200) -- the client follows the redirect
  automatically and `main.py` checks the final status code, so this needed
  no special-casing beyond the standard `status_code == 404` check already
  used elsewhere in the portfolio.

## Diff cadence

Quarterly smoke test recommended.
