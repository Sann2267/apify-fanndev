# Crawling Method — The Citizen (Tanzania)

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh at recon time (not reused from any prior check):

```
# robots.txt for https://www.thecitizen.co.tz/ -- The Citizen
User-agent: *

Disallow: /bd/
Disallow: /uganda/
Disallow: /mw/
Disallow: /rwanda/
Disallow: /tea/
Disallow: /ke/
Disallow: /kenya/
Disallow: /ms/
Disallow: /ug/
Disallow: /resource/crblob/
Disallow: /resource/themes/
Disallow: /cdn-cgi/
Disallow: /service/
Disallow: /nakuru/

Allow: /

sitemap: https://www.thecitizen.co.tz/sitemap.xml
```

Only **one** `User-agent` group exists in the file (`*`) — there is no
second/third group whose shared `Disallow:` block could be misattributed by
the "last-`User-agent`-line-only" parser bug flagged in the research doc
(the "Babak 14" postmortem). No `Claude`, `ClaudeBot`, `Claude-Web`,
`Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token appears anywhere
in the file. The `Disallow:` list is all country-syndication paths
(`/bd/`, `/uganda/`, `/mw/`, `/rwanda/`, `/ke/`, `/kenya/`, `/ug/`,
`/nakuru/` — other Nation Media Group editions' content mirrored under this
domain) plus CMS/internal paths (`/resource/crblob/`, `/cdn-cgi/`,
`/service/`) — none of which affect the `/tanzania/<section>/<slug>-<id>`
article URLs or `/sitemap.xml` this actor uses.

**Sister-site note confirmed, but does not apply here:** thecitizen.co.tz is
part of the same Nation Media Group / Mwananchi Communications Ltd stable as
`nation.africa` (Daily Nation Kenya, previously screened and found to block
Claude), and shares its CMS (same `nmgp` CSS class names, same paywall
component, and — amusingly — the 404 page's own `<title>` reads "Page not
found | **Business Daily**", the Kenyan sister paper, confirming shared
templating). Despite that, `thecitizen.co.tz`'s **own** `robots.txt` is
clean and independent of Daily Nation's — re-verified directly against this
domain, not assumed from the sibling site.

## WAF

`thecitizen.co.tz` is Cloudflare-fronted (`server: cloudflare`, `cf-ray`
header present) but shows **no active challenge**. `curl_cffi` `chrome124`
got a clean 200 on the first attempt against the homepage, `/sitemap.xml`,
and every sampled article — no `cf-mitigated` header, no bot-management
cookie (`__cf_bm`/`__cfduid`), no "Just a moment..." interstitial, no
`_cf_chl_` challenge token. The full profile ladder was not needed since
the first profile cleared immediately; a 5-request concurrent burst against
5 different article URLs also returned clean 200s with no throttling.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.thecitizen.co.tz/tanzania/<section>/<slug>-<id>` (e.g.
`/tanzania/sports/football/<slug>-5571168`, `/tanzania/news/national/<slug>-5570834`).
The page emits **two separate top-level `<script type="application/ld+json">`
blocks** — a `NewsArticle` node and a `BreadcrumbList` node — with no
`@graph` wrapper (unlike ghanaweb-scraper's single-`@graph` shape).

`NewsArticle` carries `name`, `headline`, `description` (a short
**HTML-tagged** teaser string, e.g. `"<p>...</p>"`, passed through
verbatim per the raw-passthrough convention), `image` (an array of 3
responsive-crop URLs: `landscape_ratio16x9`, `landscape_ratio3x2`,
`portrait_ratio1x1` — a different shape than ghanaweb's single image
object), `datePublished`/`dateModified`, `author` (an array of `Person`
objects with `name` + a profile `url` — **this CMS does credit individual
reporters** in ld+json, unlike GhanaWeb's `noBylinesPolicy`/`null`
pattern), and `publisher` — but **no `articleBody`**.

**Paywall metadata (the key finding of this recon):** on articles the site
marks as gated, `NewsArticle` additionally carries:

```json
"isAccessibleForFree": "False",
"hasPart": {
  "@type": "WebPageElement",
  "isAccessibleForFree": "False",
  "cssSelector": ".text-block"
}
```

Note `"False"` is a **JSON string**, not a boolean (confirmed via
`type()` on the parsed value) — a real upstream quirk, not a bug in this
actor. This flag correlates 1:1 with `news:access = Subscription` on the
same article's sitemap.xml entry.

**Despite this flag, the full article body is still server-rendered into
the HTML response regardless of subscription status.** Verified
side-by-side on two comparably-sized articles:

- Free article (`isAccessibleForFree` absent): `div.text-block.blk-txt`
  yields 16 clean paragraphs, ~3266 characters.
- `isAccessibleForFree: "False"` article: `div.text-block.blk-txt` yields
  16 clean paragraphs, ~3270 characters — the complete narrative (named
  officials, direct quotes, full argument), not a truncated teaser.

The site's paywall is enforced **client-side only** — a JS overlay appends
"Thank you for reading businessdailyafrica.com / Show plans", and later
"Register to begin your journey to our premium content / Subscribe / You
already have a Subscription? Log in" prompts to the DOM, but the real
`<p>` text was already delivered in the initial HTTP response and this
actor's paragraph-level CSS selector (`div.paragraph-wrapper > p` inside
`div.text-block.blk-txt`) excludes those prompts automatically since
they live in separate sibling elements. **Verdict: no real paywall from
this actor's perspective** — the `isAccessibleForFree`/`hasPart` fields
are still surfaced on the record for downstream awareness of which
articles the site *intends* to gate, but this scraper is not blocked
by it. This should be re-verified periodically in case the CMS moves to
a server-side truncation model.

Full text container: `div.text-block.blk-txt` — note a **second**,
much shorter `div.text-block` (single class, no `blk-txt`) also exists on
some article pages, holding only the "What you need to know:" summary
bullet (~200 characters) — selecting on **both** classes together is
required to avoid picking up the summary box instead of the real body.
Paragraphs are `<p>` tags, each individually wrapped in its own
`<div class="paragraph-wrapper">`. Ad slots
(`div.content-page-ad_wrap.mobile`/`.desktop`, containing inline
`<script>` googletag calls) and a mid-article "Related" teaser module
(`div.article-content-related`, linking to 2 other stories with their own
images/dates) are **sibling** elements at the same nesting level inside
the container — selecting `div.paragraph-wrapper > p` specifically
(rather than a blanket `get_text()` walk on the container) cleanly
excludes both with zero cleanup heuristics needed. Unlike ghanaweb's
trailing reporter-initials-signature problem, no truncation regex was
necessary here — the container is naturally clean once the right
selector is used.

Category comes from two places: `span.article-topic` (a short label,
e.g. `"National"`, `"Football"`) captured as `category`, and the
`BreadcrumbList` ld+json node (`"Home" > "News" > "National"`, or
`"Home" > "Sports" > "Football"`) captured as `categoryPath` with
`"Home"` dropped. A `section.article-content_summary` "What you need to
know:" bullet box appears on **some** articles (observed present on the
Yanga/football sample, absent on the health-insurance sample) — kept as
an optional `summary` field (label stripped via regex), null when not
present.

`meta[name=keywords]` supplies a comma-separated `keywords` string
(single-keyword or multi-keyword, inconsistent spacing after commas —
passed through verbatim, not normalized).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.thecitizen.co.tz/sitemap.xml`

Google News sitemap, the sole entry advertised via the (lowercase)
`sitemap:` line in robots.txt. Each `<url>` node carries `news:title`,
`news:publication_date` (ISO-8601 UTC), `news:keywords`
(comma-separated, inconsistent leading-space formatting — passed through
as-is), and — matching the article-page finding — `news:access`
(`"Subscription"` when present, the element is simply absent on free
articles). `image:loc` supplies a lead image URL. The feed is capped at
the ~40 newest items with no pagination/offset parameter found. Freshest
sampled item was published under 5 hours before the fetch (a live news
cycle, updates frequently but not necessarily near-real-time like
GhanaWeb's sub-minute observation).

A plain RSS 2.0 feed also exists at `/rss.xml` (confirmed real, 200,
valid `<rss version="2.0">`, ~40 items, `title`/`link`/`description`/
`pubDate`/`media:content` per item) and was considered as an alternative,
but it carries **no** `access`/paywall field and **no** `keywords` field —
strictly less information than sitemap.xml for this actor's purposes, so
sitemap.xml was chosen, matching the GhanaWeb precedent of preferring the
richer Google News sitemap when both exist. (Two other candidate paths —
`/tanzania/rss` and `/arc/outboundfeeds/rss/` — both returned HTTP 200
with `text/html` content-type and homepage-sized bodies; neither is a real
feed, just non-existent paths that resolve to a normal page rather than a
404.)

`section` is derived from the URL path (all segments between the domain
and the trailing slug-id, e.g. `"tanzania/news/national"`,
`"tanzania/sports/football"`, `"tanzania/zanzibar"`) since the sitemap
itself carries no explicit category/section element.

## Paywall verdict

**Soft paywall, not a hard block.** See the detailed finding under
"Article pages" above. `isAccessibleForFree`/`news:access` mark roughly a
third to half of sampled articles as subscription-gated, but the full
article text is delivered in the raw HTTP response regardless — this
actor recovers 100% of sampled subscription-tagged articles' text at the
same completeness as free articles. Both flags are still surfaced on
dataset records (`isAccessibleForFree`, `hasPart`, `access`) so
downstream consumers can distinguish "intended free" from "intended
premium" content even though extraction succeeds either way.

## Not-found behavior

A synthetic bad URL (`/tanzania/news/national/zzz-totally-fake-article-000000`)
returns a real **HTTP 404** with a genuine "Page not found" HTML page (no
soft-404-with-200 behavior observed). Curiously the 404 page's own
`<title>` reads "Page not found | **Business Daily**" (the Kenyan sister
paper's brand), not "The Citizen" — a shared-template artifact, harmless
to this actor since only the status code is used for error routing.

## Known limits

- Only 2 articles sampled in depth (1 free/Sports, 1
  subscription-tagged/National), plus ~15 more URLs spot-checked for
  status code and paragraph-count sanity via the sitemap. A structurally
  different template (photo gallery, live-blog, video feature, opinion
  column with a named columnist byline) was not sampled and might not fit
  the `div.text-block.blk-txt` selector, or might have a different author
  shape than the `Person`-array pattern seen here.
- The soft-paywall finding (full text always in HTTP response) was
  verified on the samples fetched during this recon session. If the site
  ever moves to server-side truncation for premium content, `articleBody`
  would silently shrink to a teaser-length string rather than crash —
  worth a periodic spot-check comparing `articleBody` length against
  `isAccessibleForFree` presence.
- `summary` ("What you need to know") appears inconsistently — no rule
  was found for which articles get one; treated as optional, null when
  absent.
- `categoryPath` relies on the `BreadcrumbList` ld+json node always being
  present; not seen missing in any sample, but no explicit `UnexpectedShape`
  guard was added for its absence (falls back to an empty list) since a
  missing breadcrumb doesn't indicate the page itself is broken the way a
  missing `NewsArticle` node or empty body does.

## Diff cadence

Quarterly smoke test recommended; re-check the soft-paywall behavior
specifically, since that's the finding most likely to change if the
publisher tightens its metering.
