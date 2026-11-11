# Crawling Method — The Motley Fool

**Last verified:** 2026-08-24

## WAF

`fool.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the RSS feed -- no challenge
body, no 403.

`robots.txt` disallows a large set of functional/paid paths
(`/account/`, `/login/`, `/investing/stocks/`, `/free-report`,
`/investor-alert/`, `/feeds` itself [ironically, though the feed still
serves 200], etc.) plus two specific bots (`MauiBot`, `Bytespider`) --
**no Claude/GPTBot/anthropic-ai disallow of any kind.** Article paths
(`/investing/<year>/<month>/<day>/<slug>/`, `/careers/...`,
`/coverage/...`) are not disallowed.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.fool.com/investing/<yyyy>/<mm>/<dd>/<slug>/`

Second actor in the portfolio (after Global Times) with **zero ld+json**
of any kind. All metadata comes from plain `<meta>` tags:
`og:title` (site-name suffix `" | The Motley Fool"` stripped),
`og:description`, `article:published_time` (proper ISO-8601),
`meta[name=author]` (single display-name string, no author-profile URL
like Rzeczpospolita's `Person.url`), `og:image`.

Full text comes from `div.article-body > p`. **Quirk:** the container
also holds `p.caption` elements -- image-attribution lines like `"Image
source: The Motley Fool."` -- that are `.decompose()`d before paragraph
extraction, otherwise they'd appear as spurious mid-article fragments.
Inline stock-ticker references (`<span class="ticker"
data-id="...">(NASDAQ: MRVL)</span>`) are left untouched -- they read
naturally as part of the sentence via plain `get_text(" ", strip=True)`.

No paywall marker of any kind was found on any sampled free article.

### 2. Latest headlines — `S2-rss`

`GET https://www.fool.com/feeds/index.aspx`

RSS 2.0, 50 items per fetch, with a `<content:encoded>` element carrying
the **full article body as HTML-escaped HTML** (the feed XML escapes the
markup as `&lt;p&gt;...&lt;/p&gt;`, not CDATA-wrapped like RT's feed) --
requires `html.unescape()` before the string is parseable HTML. Parsed
identically to the article-page body (`<p>` extraction), with one extra
filter: the **last** `<p>` in every sampled item is a `"Continue
reading"` link back to the canonical article URL and is dropped by
matching its exact lowercased text (no distinguishing class is present).

`<author>` is in the RSS-standard `email (Display Name)` shape (e.g.
`"newsfeedback@fool.com (Adam Spatacco)"`) -- the extractor keeps only
the parenthesized display name. `<link>` carries a `?source=...`
tracking param, stripped before output.

**Reliability note found during testing:** one early test run returned
only 1 of 50 items from this feed with no error raised, while every
subsequent run (including a direct raw-`lxml.etree` parse of the exact
same response) returned the full 50. No malformed XML, bad entity, or
parser discrepancy could be reproduced across `xml`/`lxml`/`html.parser`
BeautifulSoup backends on repeat fetches -- most likely a one-off
truncated/interrupted response body rather than a systematic parsing
bug. Documented here in case it recurs; no code changes were made since
it did not reproduce.

## Paywall behavior

None observed on free-tier articles (the only kind sampled). The
Premium/newsletter product line is a separate purchase flow entirely
outside `fool.com`'s public article pages and was not targeted.

## Known limits

- Only 1 article page sampled in depth for `S1-html` (a semiconductor
  stock-analysis piece), though `S2-rss` full-text extraction was
  cross-checked against 3-50 additional items across several fetches
  with consistent shape (careers, markets-recap, crypto, and
  single-stock-move article types all parsed cleanly).
- 404s are real HTTP 404s (verified with a synthetic nonexistent slug)
  -- no soft-404 behavior observed.
- `author` in article mode may be `null` for some content types (press
  releases, wire content) that don't set `meta[name=author]` -- not
  observed in the sample but not ruled out either.

## Diff cadence

Quarterly smoke test recommended.
