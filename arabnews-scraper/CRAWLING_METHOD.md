# Crawling Method — Arab News

**Last verified:** 2026-08-24

## WAF

`arabnews.com` (Drupal-based CMS) shows **no active challenge**. `curl_cffi`
`chrome124` gets a clean 200 on homepage, article pages, and the Google News
sitemap -- no challenge body, no 403.

`robots.txt` is a generic Drupal boilerplate (`Disallow: /admin/`,
`/user/login/`, etc.) with no Claude/GPTBot/anthropic-ai disallow of any kind.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.arabnews.com/node/<id>/<section>`

A single `application/ld+json` script tag with `"@type": "NewsArticle"` is
present on every article page. It **includes `articleBody` directly** --
but unlike most of this portfolio, the value is **real, un-escaped HTML
markup** (`<p>\r\n\tDUBAI: ...</p>`), not plain text and not JSON/HTML
double-escaped. The extractor parses `articleBody` with BeautifulSoup and
joins the text of every `<p>` tag with `"\n\n"` -- entity decoding
(`&nbsp;` etc.) happens automatically as a side effect of HTML parsing, no
extra `html.unescape()` pass needed.

`author` is always a single `Person` dict, frequently a wire service
(`"Reuters"`, `"AP"`, `"SPA"`) rather than a staff byline -- reflects Arab
News's heavy use of wire copy for international stories.

**No paywall observed.** No `isAccessibleForFree` field or any other
metering marker was found in any of 3 sampled articles (2 Middle East/world
stories, 1 business/economy story) -- site appears fully open-access,
ad-supported.

`articleSection` was `null` in every sample despite being present as a key
-- passed through as-is (`.get()`, no assumption it's populated).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.arabnews.com/googlenews.xml`

Google News sitemap, explicitly advertised via `Sitemap:` directive in
`robots.txt` (a second generic `sitemap.xml` also exists but isn't used
here). Minimal shape compared to other portfolio sitemaps -- each `<url>`
has only `news:title` + `news:publication_date`, **no image or keyword
blocks at all**. 147 entries present at time of writing.

## Paywall behavior

None observed anywhere in this recon.

## Known limits

- Only 3 articles sampled in depth (2 Middle East/world, 1 business). If a
  different content type (e.g. opinion/columnist pages, photo galleries)
  omits `articleBody` from its `NewsArticle` node, `UnexpectedShape` will
  raise rather than silently returning nothing.
- 404s are real HTTP 404s (verified with a synthetic out-of-range node ID)
  -- no soft-404 behavior observed, unlike `business-standard-scraper`.

## Diff cadence

Quarterly smoke test recommended.
