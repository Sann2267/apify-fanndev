# Crawling Method — The Namibian

**Last verified:** 2026-08-26

## robots.txt (re-verified per stop-condition check)

```
# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow: /?s=
Disallow: /page/*/?s=
Disallow: /search/
Disallow: /wp-json/
Disallow: /?rest_route=

User-agent: AdsBot
Disallow: /

Sitemap: https://www.namibian.com.na/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

Two `User-agent` groups, each with its own `Disallow` block directly
beneath it (Yoast SEO's standard emission, `AdsBot`'s `Disallow: /` is a
separate, self-contained group -- not merged with `*`'s block, so the
Babak-14 false-clean parser bug pattern flagged in the research doc does
not apply here). Both groups were read individually. No `Claude`,
`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` token appears anywhere in the file, under any group. None
of the `*`-group disallows (`/?s=`, `/page/*/?s=`, `/search/`, `/wp-json/`,
`/?rest_route=`) affect article URLs (`/<slug>/`) or the RSS feed
(`/feed/`) this actor uses. `AdsBot`'s full disallow is irrelevant since
this actor never identifies as AdsBot.

## WAF

`namibian.com.na` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on the homepage, staff-written article pages,
wire-service (AFP) article pages, editorial pieces, the RSS feed, and a
synthetic 404 test. The site is nginx + CloudFront fronted
(`x-cache: Hit/Miss from cloudfront`, `x-amz-cf-pop`, `x-amz-cf-id`
headers, `via: ... cloudfront.net`), but that's CDN plumbing only -- no
`_abck`/`bm_sz`/`_px3`/`_pxhd`/`_dd_s`/`__cf_bm`/`cf-ray` cookie or header
was ever set, no challenge body, no 403/429/503 on any of the ~10 URLs
sampled. Since the baseline profile already succeeds cleanly, the full
impersonation ladder was not needed (principle #2 is for escalating past
a block, not for a target that already works).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.namibian.com.na/<slug>/` (WordPress + Yoast SEO; no
numeric ID in the URL, routing is purely by slug).

The page emits **one ld+json `@graph` array** holding an `Article` node,
a `WebPage` node, a `BreadcrumbList` node, one `ImageObject` node (the
lead/primary image), a `WebSite` node, an `Organization` node, and one or
more `Person` nodes -- one per byline. Unlike ghanaweb-scraper's
`NewsArticle` node (where `author` is an inline object), here **`author`
and `image` on the `Article` node are `@id` references** into the same
graph (`{"@id": "https://www.namibian.com.na/#/schema/person/<hash>"}`),
so the extractor builds an `@id` -> node lookup across the whole graph
and resolves both. `wordCount` is present and reliable (spot-checked
against the extracted body's own word count -- matches within a normal
few-word margin from headline/subhead differences). `articleSection` is
an **array** of WordPress category names assigned to the post (e.g.
`["National","News","Top Story 1"]`, `["Business","Business Home 3"]`),
not a single clean category the way ghanaweb-scraper's is -- passed
through as-is per the raw-passthrough rule rather than picking "the"
category. **No `articleBody`** in ld+json, same as ghanaweb.

`author` resolution covers three cases, all via the same `Person`-node
lookup (no special-casing needed): a named staff reporter (e.g. "Chris
Kaukemua", "Werner Menges"), a wire service credited as if it were a
person (e.g. "AFP" -- confirmed via a live rugby wire story), and the
outlet's own name on unsigned editorial pieces (e.g. "The Namibian" on
`/cabinet-overreach-can-endanger-good-governance/`). There is no
GhanaWeb-style `noBylinesPolicy` signal distinguishing staff from wire in
ld+json; cross-reference the RSS `<dc:creator>` field (from latest mode)
if that distinction matters downstream -- it carries the same names.

Full text comes from HTML: `div.entry-content` (real WordPress Gutenberg
block markup -- `<p class="wp-block-paragraph">` tags, genuinely
paragraph-per-`<p>`, unlike GhanaWeb/Global Times' single-`<p>`-with-
`<br>` legacy blob). Paragraphs are extracted with a plain `find_all("p")`
walk and joined with a blank line. No trailing reporter-initials
signature or promo/embed noise was found on any sampled article (staff
news, wire/AFP sport, business, or unsigned editorial) -- the full
paragraph list from `div.entry-content` is the real body as-is, no
truncation heuristic needed (simpler than ghanaweb's byline-signature
cutoff).

Encoding: `Content-Type: text/html; charset=UTF-8` is correctly declared
and correctly followed -- raw bytes for smart quotes/em-dashes are valid
UTF-8 (`\xe2\x80\x9c` etc.). Garbled-looking `�` characters seen in ad hoc
terminal `print()` output during recon were a **Windows console codepage
display artifact only**, not a real encoding problem in the scraped data
(confirmed by inspecting `response.content` raw bytes directly) -- no
special handling needed in the extractor.

### 2. Latest headlines — `S2-rss`

`GET https://www.namibian.com.na/feed/` (WordPress's default theme feed;
not referenced in `robots.txt` but not disallowed by it either -- none of
the `*`-group's five `Disallow` rules match `/feed/`).

Standard WordPress RSS 2.0: `title`, `link`, `dc:creator`, `pubDate`
(RFC-822), `category` (one `<category>` element per item on every item
sampled), `guid` (WordPress's internal `?p=<id>` permalink, stable across
slug changes), `description` (short excerpt, ends in an ellipsis + a
"The post ... appeared first on The Namibian." boilerplate paragraph),
and — the key quirk this actor exploits — **`content:encoded` carrying
the full article body HTML**. Verified identical (same paragraphs, same
wording) to the `div.entry-content` HTML pulled by the `S1-html` article
strategy on the same article. This means **latest mode returns complete
article text with zero extra per-item HTTP requests**, unlike
ghanaweb-scraper's Google News sitemap (headline metadata only, still
needs a separate per-article fetch for body text).

`content:encoded` always ends with a fixed WordPress-generated paragraph
-- `<p>The post <a href="...">Title</a> appeared first on <a
href="...">The Namibian</a>.</p>` -- appended by the "Multiple Post
Thumbnails" / core feed-content filter behavior; this is boilerplate, not
article content, and is stripped by checking each paragraph's text for
both `"The post "` and `"appeared first on"` substrings (plain string
check, not a regex, since the wording is fixed across every item
sampled).

**Pagination quirk (found and fixed):** the feed paginates via
`?paged=N`, 12 items per page, but **consecutive pages overlap by exactly
one item** -- the last item on page 1 (`guid=...?p=967705`, "Namibia
joins Mercedes-Benz global anniversary drive") reappeared as the first
item on page 2 in a live test requesting `limit=15`. Root cause not
confirmed with certainty, but consistent with two posts sharing the same
`pubDate` second and the feed's stable-sort boundary landing mid-tie.
`fetch_latest()` dedupes across pages by `guid` while accumulating items,
so a `limit` above 12 never emits a duplicate record. No `robots.txt`
constraint on `/feed/?paged=N`.

No Google News sitemap was found in `robots.txt`'s `Sitemap:` line --
only the Yoast SEO structural `sitemap_index.xml` (`post-sitemap.xml`
through `post-sitemap4.xml`, no `lastmod`-only entries, no `news:*`
namespace, no per-item title/date beyond `<lastmod>`) -- unlike
ghanaweb-scraper's dedicated `/sitemaps/news.xml`. The RSS feed is
therefore the correct and richer `latest`-mode source here; the Yoast
post-sitemaps were not used.

## Paywall behavior

**None observed — fully free.** No `isAccessibleForFree`, "paywall",
"premium", "member-only", or "metered" marker was found in raw HTML or
ld+json on any of the ~10 sampled pages spanning National, Business,
Sport, Crime, and Editorial/Opinion sections. A `/digital-subscription/`
page and a "Subscribe Now" link exist in the site nav (pointing at
`esubs.namibian.com.na`, an e-paper/PDF-edition subscription product,
separate from the free HTML article site), but they never gate article
body content -- full body text was retrieved identically on every sample,
including business/finance pieces that are often paywalled at other
outlets.

## Known limits

- Only ~10 articles sampled in depth across National, Business, Sport
  (wire/AFP), Crime, and Editorial/Opinion sections. A structurally
  different template (photo gallery, live-blog, video feature, the
  Oshiwambo-language Friday section mentioned in the site's own Yoast
  meta description) was not sampled and might not fit the
  `div.entry-content` selector or the single-`Article`-ld+json-block
  assumption.
- `articleSection` is passed through as the raw WordPress category array,
  which mixes genuine section names (`"National"`, `"Business"`,
  `"Sport"`) with homepage-placement pseudo-categories (`"Top Story 1"`,
  `"Business Home 3"`, `"More Top Stories"`) -- downstream consumers
  wanting a single clean category must filter this list themselves; no
  attempt was made to guess which array element is "the real" category.
- RSS pagination dedup is by `guid` only; if WordPress ever changes guid
  format (e.g. switches to slug-based guids) mid-run, this would still
  work since it's just an equality check on whatever string the feed
  returns -- no format assumption baked in beyond "unique per post."
- `wordCount` in ld+json is upstream-reported, not independently verified
  against the extracted `articleBody`; used as raw passthrough with no
  cross-check enforcement in the extractor.

## Diff cadence

Quarterly smoke test recommended.
