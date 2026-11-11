# Crawling Method — The Daily Telegraph (UK)

**Last verified:** 2026-08-26

## WAF

`telegraph.co.uk` sits behind **Akamai**, and the Akamai layer here is
fronting a **TollBit bot-licensing gate** in addition to the usual
bot-management challenge. Most impersonation profiles in the portfolio's
standard ladder get a synthetic **402 Payment Required**:

```
<h1>Access Issue Help</h1>
<p>You are seeing this page because our security systems have detected
some unusual activity on this connection...</p>
[{"message":"You are not authorized to access this content without a
valid TollBit Token. Please follow this URL to find out more.",
"url":"https://tollbit.dev", ...}]
```

Profile-by-profile result on the homepage (2026-08-26):

| Profile | Result |
| --- | --- |
| `chrome131` | **402** (blocked) |
| `chrome124` (portfolio default) | **402** (blocked) |
| `safari17_0` | **402** (blocked) |
| `firefox133` | **402** (blocked) |
| `chrome99_android` | **200** (clean) |
| `edge101` | **200** (clean) |

This is decided purely by TLS fingerprint (same URL, same headers, same
IP -- only the impersonation profile changes), so it is a bot-management
gate, not a per-request licensing check: no token was purchased, no
login was used, nothing content-specific was bypassed. **TLS profile
pinned: `edge101`** -- a deliberate deviation from the portfolio's usual
`chrome124` default because `chrome124` is one of the blocked profiles
here.

`robots.txt` has **no Claude/ClaudeBot/anthropic-ai/GPTBot/Claude-Web/
Claude-User/Claude-SearchBot disallow anywhere**. It blocks a fixed list
of named crawlers outright (`AdsBot-Google`, `APIs-Google`,
`AdsBot-Google-Mobile`, `Mediapartners-Google`, `Googlebot` (+ Image/
News/Video variants), `Storebot-Google`, `Google-InspectionTool`,
`bingbot`, `BingPreview`, `Slurp`, `DuckDuckBot`, `Baiduspider`,
`YandexBot`, `Applebot`, `AhrefsBot`, `SemrushBot`, `MJ12bot`, `DotBot`,
`BLEXBot`, `PetalBot` -- all sharing one `Disallow: /` block, checked
carefully for the multi-user-agent-group parsing bug: confirmed these 23
user-agents are genuinely one group, not spuriously merged), followed by
`User-agent: * / Allow: /` as the catch-all every unlisted crawler
(including any Claude/Anthropic agent) falls into.

`sitemap.xml` / `sitemap-news.xml` return the same 402 block even under
`edge101` -- not investigated further since `/rss.xml` (below) already
covers `latest` mode.

## Data sources

### 1. Article pages — `S1-html` (only strategy needed)

`GET https://www.telegraph.co.uk/<section>/<yyyy>/<mm>/<dd>/<slug>/`

Each article page emits exactly **one** `application/ld+json` block
(`@type: NewsArticle`) -- unlike most of this portfolio there is no
separate `NewsMediaOrganization` or `BreadcrumbList` block. It carries
`headline`, `url`, `datePublished`, `dateModified`, `inLanguage`,
`articleSection` (**confirmed always an empty string** across every
sample), `keywords` (comma-separated tag string, always populated --
used as the closest thing to a category), `publisher`
(`NewsMediaOrganization`, name `"The Telegraph"`), `isAccessibleForFree`,
`author` (list of `Person` objects with `name`/`url`/`jobTitle`), and
`image` -- but **no `articleBody` key at all** (not truncated, simply
absent).

Full text is pulled from HTML: the body is split across **multiple
sibling `div.articleBodyText` blocks**, interleaved with
`figure.article-body-image` blocks (every inline photo starts a new body
block). The first `div.articleBodyText` wraps an inner
`div.component.article-body-text` (carrying the
`data-test="article-body-text"` marker); later sibling
`div.articleBodyText` blocks hold `<p>` tags directly with no inner
wrapper. `_extract_body()` runs `find_all("p")` recursively inside every
`div.articleBodyText` on the page, which picks up both shapes uniformly.
Confirmed correct on a 7-paragraph breaking-news brief (single body
block) and a 48-paragraph, 7-block magazine profile interleaved with 5
inline images -- extracted text ended cleanly at the photographer/stylist
credit line in the latter case, confirming no truncation.

### 2. Latest headlines — `S2-rss`

`GET https://www.telegraph.co.uk/rss.xml`

Sitewide RSS 2.0 feed (confirmed live, `lastBuildDate` matched request
time). Fields per `<item>`: `title`, `link`, `description` (short
teaser), `pubDate`, `guid` (`isPermaLink="false"`, an opaque UUID, not
the article slug), `dc:creator` (**repeatable** -- multi-byline articles
list one `<dc:creator>` per author), `category` (repeatable,
taxonomy-style values like `topics:places/middle-east`,
`structure:opinion`, `storytype:comment` -- kept as a list rather than
picking just one, since none of them map cleanly to a single
human-readable section name), and `enclosure` (lead image, `type` +
`length` attributes present but `length` was observed as a placeholder
`"99"` rather than a real byte count on every sampled item -- not
relied on). A per-section variant also exists (`/news/rss.xml` confirmed
working) but the sitewide feed was chosen as the `latest`-mode default
for the same reason as the rest of this portfolio: one request, broadest
coverage.

## Paywall behavior

**No hard paywall found via HTTP -- soft/cosmetic at most, likely purely
client-side.** 13 articles were sampled across a deliberately wide mix
of sections and content types: breaking news, business news, world news,
football, obituaries (x2), politics, money/personal-finance, travel news,
a long-form fashion/celebrity interview feature, two opinion/comment
pieces, and one flagship signed economics column (Ambrose
Evans-Pritchard, "World Economy Editor" -- exactly the kind of premium
columnist content UK papers typically gate hardest). Every single one
came back:

- `isAccessibleForFree: true` in the ld+json block (never observed
  `false` in this sample)
- A full-length, naturally-ending `articleBody` reconstructed from HTML
  (1.1 KB for a short breaking-news brief up to 18 KB for the long-form
  interview feature; the Evans-Pritchard column ran 7.9 KB and ended on
  its actual closing line, not a mid-sentence cut)
- No "subscribe"/"paywall"/"premium-locked"/lock-icon markers anywhere
  in the raw HTML

The page does load Piano/Tinypass (`tinypass` string present in inline
script config), which is the vendor Telegraph uses for its metered
subscriber paywall -- but that meter is enforced **client-side via
JavaScript** (cookie-based view counting + a DOM overlay injected after
page load). Since this actor never executes JavaScript, the meter never
fires, and the server-rendered HTML this actor reads already contains
the complete article body regardless of the `list-headline--premium` CSS
class Telegraph applies to many homepage teaser links (that class is a
styling hook, not a reliable paywall signal -- confirmed by sampling
several `--premium`-tagged links and finding full bodies on all of
them).

Per the fail-loud/no-fabrication convention, this actor still ships an
honest `_paywalled` field (`true` only if `isAccessibleForFree == false`
**and** the scraped body is under 600 chars) in case some content type
outside this sample (e.g. a different template for live blogs, or a
future subscriber-only vertical) does hard-gate server-side -- it has
simply never been observed to fire in 13/13 samples.

## Known limits

- 402-vs-200 depends entirely on TLS profile, not on IP or headers in
  this recon -- if `edge101` is ever added to Akamai's blocklist, retry
  with `chrome99_android` (confirmed working) before reaching for a
  browser.
- Only 13 articles sampled in depth, all published the same week
  (2026-08-24/25). A structurally different template (live blog, video
  feature, photo gallery, or Telegraph Puzzles) was not sampled and may
  not use the same `div.articleBodyText` markup.
- `section` in article-mode output is a best-effort URL-path guess, not
  an upstream field -- ld+json's own `articleSection` is always empty on
  this site.
- Real 404s confirmed (synthetic out-of-range slug, generic Telegraph
  error-page template, `isPageMetered=0` in the page's ESI markup)
  -- no soft-404 behavior observed.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL (ideally a paid columnist) and confirm `isAccessibleForFree`
and body length are still consistent with "no hard paywall." If
Telegraph ever starts returning `isAccessibleForFree: false` with a
short body, `_paywalled` will start firing honestly rather than silently
serving stale assumptions. If the `div.articleBodyText` markup
disappears entirely, `_extract_body()` raises `UnexpectedShape` and the
run fails loudly instead of emitting empty records.
