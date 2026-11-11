# Crawling Method — China Daily

**Last verified:** 2026-08-25

## WAF

`chinadaily.com.cn` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on the homepage, article pages, section listing pages,
and a synthetic-404 test URL -- no challenge body, no 403.

`robots.txt` itself is a real HTTP 404 (not an empty file -- confirmed by
body: it serves the site's generic 404 page, same shape as a missing
article page) -- treated as "no crawl restrictions stated," same
convention as the rest of this portfolio for sites without a robots.txt.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.chinadaily.com.cn/a/<YYYYMM>/<DD>/WS<hex id>.html`

The page emits a single `<script type="application/ld+json">` tag typed
`NewsArticle` (confirmed on all 4 sampled articles -- unlike TASS there's
no `Organization`/`SiteNavigationElement` clutter to scan past, but the
extractor still scans all ld+json blocks and picks the one whose `@type`
is `NewsArticle`, for robustness against a future template that adds
more blocks). It carries `headline`, `image`, `datePublished`,
`dateModified`, `publisher` (`Organization`, name inconsistently either
`"China Daily"` or `"chinadaily.com.cn"` depending on which CMS template
rendered the page -- passed through raw, not normalized), and sometimes
`author` (`Person`) and `description` -- both absent on wire-service/
Xinhua-sourced content with no named byline (confirmed on one sample).
**No `articleBody`** in ld+json, same limitation as TASS.

Full text comes from HTML `#Content` -- this element ID is stable across
at least 3 different CMS template generations seen in sampling (an older
`class="info"` byline template, a newer `class="Artical_Content"`
template, and a video-article template), while the *class* on that div is
NOT stable, so extraction selects by `id`. Paragraphs are plain
unwrapped `<p>` tags (like TASS, not the `<br>`-separated Global Times
style) -- the lead image's `<figcaption>` sits as a sibling of the `<p>`
tags rather than inside one, so it's naturally excluded by selecting only
`<p>` tags (no explicit `.decompose()` step needed, unlike Global Times'
duplicate picture caption).

No paywall marker of any kind was found (state media, fully open-access).

### 2. Latest headlines — `S2-html-listing`

`GET https://www.chinadaily.com.cn/` (homepage)

`/rss/china_rss.xml` and `/sitemap.xml` both return HTTP 200 but are
**dead/frozen artifacts** -- the RSS feed's newest item is dated December
2017 and the sitemap's newest `lastmod` is from 2014. Neither is usable
for "latest" mode.

Instead the homepage is scraped for `<a href>` links matching the article
URL pattern `/a/YYYYMM/DD/WS<hex>.html`. Because that ID is zero-padded
and chronological, sorting the URLs lexically descending reproduces
newest-first order without visiting each article page. Each link appears
twice in the markup (once wrapping a thumbnail `<img>` with no text, once
wrapping the headline text) -- the extractor keeps the longest non-empty
anchor text seen for a given URL as the title. `urlDate` (day precision
only) is derived from the URL path itself, not a true publish timestamp --
fetch the article (`article` mode) for the exact `datePublished` from its
ld+json block.

## Paywall behavior

None observed. Chinese state media, fully open-access.

## Known limits

- Some "photo essay" articles paginate their body across multiple pages
  (`..._2.html`, `..._3.html`, ...) -- only page 1's paragraphs are
  captured by this extractor.
- A handful of `/subsites/...`-style sponsored microsite pages use a
  completely different template with no ld+json and no `#Content` div at
  all -- these correctly raise `UnexpectedShape` (fail loud) rather than
  being silently guessed at.
- `description`/`author` are `null` on wire-service (Xinhua) content with
  no named byline -- this is a real absence in the source, not a parsing
  bug.
- 404s are real HTTP 404s (verified with a synthetic hex ID) -- no
  soft-404 behavior observed.

## Diff cadence

Quarterly smoke test recommended.
