# Crawling Method — Euronews

**Last verified:** 2026-08-25

## WAF

`euronews.com` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on homepage (~600KB), article pages (~400KB), and the RSS
feed -- no challenge body, no 403.

`robots.txt` (`https://www.euronews.com/robots.txt`, 200) has a generic
`User-agent: *` block (`Disallow: /api/`, `/login`, `/register`, various
internal paths, weather pagination) followed by `Allow: /`, plus a
named-bot section listing `OAI-SearchBot`, `ChatGPT-User`,
`PerplexityBot`, `FirecrawlAgent`, `AndiBot`, `ExaBot`, `PhindBot`,
`YouBot` (all explicitly allowed) and a separate block disallowing
`GPTBot`, `CCBot`, and `Google-Extended` entirely (`Disallow: /`). No
Claude/ClaudeBot/anthropic-ai/claude-web/claude-user/claude-searchbot
entry of any kind -- unrestricted under the generic `Allow: /` rule.

Four sitemaps are declared: `sitemaps/en/sitemap.xml`, `articles.xml`,
`videos.xml`, `images.xml` -- not used by this actor since the RSS feed
already covers the `latest` use case, but available if sitemap-based
backfill is ever needed.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.euronews.com/<section>/<yyyy>/<mm>/<dd>/<slug>`

The page emits **2 separate ld+json blocks**: the first is
`{"@context": ..., "@graph": [NewsArticle, WebSite, Organization]}`; the
second is a standalone `BreadcrumbList` block. The extractor scans the
`@graph` array for the `NewsArticle` entry (`headline`, `description`,
`articleBody`, `inLanguage`, `dateCreated`/`dateModified`/
`datePublished`, `image` (`ImageObject` with a `url` field), `author`
(a **list** of `Person` objects -- byline is individual, not agency,
unlike TASS -- `familyName`/`givenName`/`name`/`url` profile link),
`articleSection` (list, single element in all samples), and `speakable`)
and, separately, the `Organization` entry (`name: "Euronews"`) -- needed
because `NewsArticle.publisher` is only a bare `{"@id":
"https://www.euronews.com/#organization"}` reference, not an inline
object with a `name`.

**Known quirk:** the ld+json `articleBody` string has paragraph breaks
stripped -- in the sampled Danish care-home article, `"...said on
Monday.The 13 individuals..."` has **zero characters** between the
period and the next sentence, i.e. paragraphs are concatenated with no
separator at all. Because of this, full text is pulled from HTML
`div.c-article-content > p` instead (**direct-child** `<p>` tags only).
That container also holds interleaved `<div>` elements (an
`ADVERTISEMENT` slot, a `connatix-container` video-ad embed, and a
`c-widget-related` "Related" links box) and occasional `<h2>`
subheadings -- confirmed on 3 sampled articles that none of those
`<div>`s carry nested `<p>` tags, so `recursive=False` on the `<p>`
scan is a safety margin against future drift, not a current necessity.
`<h2>` subheadings are intentionally dropped from `articleBody` (minor,
documented content loss -- e.g. one sampled article had a
"Turning up the heat" subhead that doesn't appear in the output).

No paywall marker of any kind was found (`paywall`, `subscribe`,
`subscription-required`, `metered`, `premium-content` all absent from
page text on every sample) -- euronews.com is fully open-access,
consistent with its EU/broadcaster-funded editorial model.

### 2. Latest headlines — `S2-rss`

`GET https://www.euronews.com/rss`

Standard RSS 2.0: `title`, `link`, `guid`, `pubDate`, `description`
(short teaser, not full article text). **No `<category>` field**
(unlike TASS's RSS feed), so `latest` mode output has no section/
category column. 50 items returned per fetch.

**Quirk:** the feed mixes text-article links with `/video/...`
news-bulletin links. Video pages return 200 but carry a `VideoObject`
ld+json block instead of `NewsArticle` -- feeding one of those links
into `article` mode correctly raises `UnexpectedShape` ("No NewsArticle
ld+json block found"), which propagates and fails the run loudly rather
than silently emitting an empty-body record. This is expected/desired
behavior per the fail-loud convention, not a bug -- `article` mode is
for text articles only.

## Paywall behavior

None observed. Euronews is EU/broadcaster-funded and fully open-access
for text content.

## Known limits

- `description` in `latest` mode is a teaser, not the full article body
  -- use `article` mode against the `link` for full text.
- 404s are real HTTP 404s (verified with a synthetic nonexistent
  article slug) -- no soft-404 behavior observed. The 404 page body
  contains an obfuscated third-party ad-loader script
  (`html-load.com/main.js`) that also appears on normal 200 pages --
  it is an ad/analytics loader, not a bot-detection challenge, and is
  not treated as a block marker.
- `<h2>` subheadings inside the article body are dropped from
  `articleBody` -- only `<p>` paragraph text is captured.
- `/video/...` URLs in `article` mode will raise `UnexpectedShape` by
  design (see quirk above) -- this actor only extracts text articles.
- Only 3 articles sampled in depth (a short abuse-compensation brief, a
  longer Houthis/Red Sea story with embedded ad/related widgets, and a
  business/insolvency story). All three shared the same
  `div.c-article-content` / `@graph` markup pattern.

## Diff cadence

Quarterly smoke test recommended.
