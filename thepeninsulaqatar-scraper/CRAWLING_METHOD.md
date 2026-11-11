# Crawling Method — The Peninsula (Qatar)

**Last verified:** 2026-08-26

## robots.txt

Fetched `https://thepeninsulaqatar.com/robots.txt` directly (8,661 bytes,
458 lines). It has two parts:

1. A `User-agent: *` block (top) disallowing CMS/admin paths (`/admin/`,
   `/cgi-bin/`, `/dev/`, `/vendor/`, install scripts, tracking-parameter
   query strings, etc.) -- none of which affect `/article/<dd>/<mm>/<yyyy>/<slug>`
   URLs or `/sitemap*.xml`.
2. A long "Bad-Robots" denylist (~140 groups) of ancient scraping tools and
   generic bots (`Wget`, `TeleportPro`, `EmailCollector`, `CherryPicker`,
   `HTTrack`-style tools, `ia_archiver`, `CCBot`, `SemrushBot`, `mj12bot`,
   `AhrefsBot`, etc.) -- checked **every single group line-by-line** for
   the multi-user-agent-group parser bug (several `User-agent:` lines
   sharing one `Disallow:` block below them): **every group here has its
   own individual `User-agent:` / `Disallow:/` pair**, no shared blocks
   spanning multiple robots. No grouping bug present.

Searched the entire file (case-insensitive) for `claude`, `anthropic`,
`gptbot`, `ccbot`, `google-extended` -- **only `CCBot` appears** (line
349, its own individual group, `Disallow:/`), and it is not
Claude/Anthropic. **No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` entry anywhere in the file.**
No `Sitemap:` directive is advertised (the real sitemap was found by
probing the conventional `/sitemap.xml` path directly).

**Verdict: robots.txt is clean.** Built per the go-ahead in the research
doc's Babak 14 candidate list.

## WAF

`thepeninsulaqatar.com` sits behind Cloudflare (`server: cloudflare`,
`cf-ray` header present on every response) but shows **no active
challenge**. `curl_cffi` `chrome124` gets a clean 200 on the homepage
(~190 KB, brotli-encoded), article pages (~130-140 KB), `/sitemap.xml`,
and every monthly sitemap shard tested -- no "Just a moment" interstitial,
no 403, no captcha marker in any response body.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile ladder needed -- the first profile tried worked
cleanly.

## Data sources

### 1. Article pages — `S1-html`

`GET https://thepeninsulaqatar.com/article/<dd>/<mm>/<yyyy>/<slug>`

The page emits exactly **one** `<script type="application/ld+json">`
block, and it is a **site-wide `WebPage` navigation schema** (the
homepage's `@id`, a `sameAs` social-links array, and a `hasPart` list of
the site's category pages) -- **identical on every article sampled**,
carrying zero per-article data. There is no `NewsArticle`/`Article`
ld+json block anywhere on this site. All per-article data instead comes
from `<meta>` tags (the template repeats the same values across four
parallel families: `itemprop=*`, `article:*`, `DC.*`, `og:*`/`twitter:*`
-- `itemprop`/`og:*` used as primary source, others as fallback) plus two
stable HTML anchors:

- `h3.title-tag` -- breadcrumb navigation, exactly two `<a>` tags:
  main category (`"Qatar"`, `"World"`, ...) and subcategory
  (`"General"`, `"Americas"`, `"Europe"`, ...).
- `h5.title` (inside `div.in-title`) -- the actual per-article byline/
  wire-source tag. Confirmed values across samples: `"QNA"` (Qatar News
  Agency), `"AFP"`, and `"The Peninsula"` (staff-written). This is
  mapped to the `author` output field. The `article:author`/
  `itemprop=author` meta tags, by contrast, carry the **same generic
  value on every article** (`"The Peninsula Newspaper"`) -- an org name,
  not a byline -- mapped to `publisher` instead so the two aren't
  conflated.

Full article text lives in `div.con-text`. The template emits **exactly
two** of these per page: the first is always empty (an artifact of a
share-widget wrapper), the second holds the real paragraphs. Raw HTML
wraps each article's paragraphs in one stray outer `<p>` around all the
real `<p>` tags (`<p> <p>real text</p><p>more text</p> </p>`) --
`BeautifulSoup(html, "lxml")` auto-closes the malformed outer tag during
parsing, so collecting *direct-child* `<p>`/`<h2>`/`<h3>`/`<blockquote>`
tags of each `div.con-text` already yields clean, correctly-split
paragraphs with no manual unwrapping needed. Verified clean (no ad/embed
leakage -- no `<iframe>`, `<script>`, `<ins>`, or nested `<div>` found
inside any sampled `div.con-text`) on 4 samples: a long-form Qatar
Museums feature (16 paragraphs, "The Peninsula" byline), a short
Canada-tariffs wire brief (4 paragraphs, "QNA" byline), a Belgium
disappearance wire story (9 paragraphs, "AFP" byline), and a Qatar
diplomacy piece (7 paragraphs) -- spanning three different wire sources
and three different section/subsection combinations (Qatar/General,
World/Americas, World/Europe), all sharing the identical template.

`datePublished`/`dateModified` come from the `itemprop`/`article:*` meta
tags as **raw strings** (`"2026-08-25 19:46:52"`) -- Doha local time
(UTC+3, no DST), but the site does not expose an explicit UTC-offset
marker on this value anywhere, so it is passed through as-is rather than
guessing a timezone suffix onto it (raw-passthrough discipline).

### 2. Latest headlines — `S2-sitemap`

`https://thepeninsulaqatar.com/sitemap.xml` is a `<sitemapindex>` of
**monthly-sharded** article sitemaps going back to at least 2024
(`/sitemap_articles-<year>-<month>.xml`, month with **no leading zero**,
e.g. `sitemap_articles-2026-8.xml`). Each shard is a proper Google News
sitemap (`xmlns:news`) with `news:title`, `news:publication_date`,
`lastmod`, and `loc` per `<url>` entry. The August 2026 shard contains
1,397 URLs and is confirmed **newest-first** (top entry dated
2026-08-25/26, descending to 2026-08-01 at the bottom) -- no re-sorting
needed, just slice `[:limit]`.

**No RSS feed exists.** `/feed`, `/feed/`, `/rss`, `/rss.xml`, and
`/rss/<section>.xml` were all probed and every one returns **HTTP 200**
with the site's generic catch-all listing template (~93 KB HTML, no
`<title>`, `content-type: text/html`) instead of a 404 or real feed --
a soft-200, not a working feed. `/sitemap_index.xml`, `/news-sitemap.xml`,
`/sitemap-news.xml`, and `/sitemap_news.xml` (common convention guesses)
all soft-200 to the same generic template too -- only the exact path
`/sitemap.xml` is real. This is why `latest` mode reads the sitemap
instead of an RSS feed.

`fetch_latest()` requests the current UTC month's shard and, if it comes
back with fewer than `limit` items (e.g. run on the 1st-2nd of a new
month before many articles have posted), also fetches the previous
month's shard and extends the list before slicing to `limit`.

## Paywall behavior

None observed. No "subscribe"/"paywall"/"premium"/"member-only"/"sign in
to continue" markers found in raw HTML on any of the 4 sampled full
articles, and no upstream `isAccessibleForFree`-style flag exists at all
(there being no ld+json `NewsArticle` block to carry one) -- the site
appears to be fully open-access, ad-supported.

## Known limits

- No ld+json article data exists on this site at all -- every field is
  either a `<meta>` tag or an HTML anchor selector. If the site ever
  redesigns its template (`div.con-text`, `h3.title-tag`, `h5.title`
  class names), extraction breaks loudly (`UnexpectedShape`) rather than
  silently.
- `datePublished`/`dateModified` are raw Doha-local strings with no
  explicit timezone marker in the upstream value itself -- don't assume
  UTC when sorting/filtering on these fields downstream.
- `description` is only populated in article mode (from `<meta
  name="description">`); latest-mode sitemap entries carry no summary
  text, only `title`/`link`/`pubDate`/`lastmod`.
- 404s are real HTTP 404s (verified with a synthetic
  `/article/01/01/2020/this-is-a-bogus-nonexistent-article-slug-xyz123`,
  93 KB generic error page, `News | The Peninsula Qatar` title) -- no
  soft-404 behavior observed on the `/article/...` path itself (soft-200s
  were only found on the RSS/sitemap-guess paths listed above, not on
  article URLs).
- Only 4 articles sampled in depth (1 staff-written feature, 2 wire
  stories via QNA/AFP, 1 diplomacy brief), all sharing the exact same
  `div.con-text` / `h3.title-tag` / `h5.title` markup. A structurally
  different template (live-blog, video feature, photo gallery, opinion
  column) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
