# Crawling Method — Mail & Guardian (South Africa)

**Last verified:** 2026-08-24

## WAF

`mg.co.za` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the RSS feed -- no challenge
body, no 403.

`robots.txt` is minimal: `Allow: /` for `User-Agent: *` (only `/_next/`
disallowed), and a **dedicated `Google-Extended` block that also just says
`Allow: /`** -- i.e. this site explicitly opts IN to Google's AI-training
crawler rather than opting out. No Claude/GPTBot/anthropic-ai disallow of
any kind.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://mg.co.za/<section>/<yyyy-mm-dd>-<slug>/`

A `NewsArticle` ld+json block carries rich metadata (`headline`,
`description`, `author` as a list, `keywords`, `image` as a list,
`wordCount`, dates) but **no `articleBody` field**. Body text is scraped
from HTML: every `<p>` tag inside the page's `<article>` element --
unlike `independent-scraper`/`eluniversal-scraper`, **no UI boilerplate,
ad placeholders, or promo CTAs were found mixed into the `<article>`
container** in either of the 2 sampled articles (35 and 25 real paragraphs
respectively, first and last both genuine body text) -- a plain
`find_all("p")` join is sufficient, no filtering needed.

`keywords` arrives as a comma-separated string, split into a list to match
the shape used elsewhere in this portfolio. `author` and `image` are both
JSON arrays (`author` sometimes has multiple contributors, though both
samples had exactly one) -- the first `image` entry's `url` is used as the
lead image. No `isAccessibleForFree` or other paywall marker was found.

### 2. Latest headlines — `S2-rss`

`GET https://mg.co.za/rss/`

**Not advertised in `robots.txt`** -- only `Sitemap: https://mg.co.za/
sitemap.xml` is listed there, and that sitemap tree turned out to be
**title-less**: it's a `sitemapindex` of per-category sitemaps, each of
which lists individual article `<url>` entries with only `loc` + `lastmod`
(no `news:news` block, no title, despite the `xmlns:news` namespace being
declared on the root `<urlset>` tag). Since fetching a title would require
visiting each article page individually -- defeating the point of a
"latest headlines without visiting each article" mode -- `/rss/` was
found by direct path probing instead (`/feed/`, `/rss.xml`, and
`/news/feed/` all 404; `/rss/` returned a valid `application/rss+xml`
feed, 50 items).

Standard RSS shape: `title`, `link`, `guid`, `pubDate`, `description` (a
short teaser -- genuinely different wording from the ld+json `description`
on the article page itself, not a duplicate). `content:encoded` is present
but deliberately NOT used -- it's just the same teaser wrapped in `<p>`
tags plus a boilerplate "Read the full article" link, no additional body
text. The `<enclosure>` tag's `url` attribute is the lead image; its
`type` attribute is a **CMS bug** (it duplicates the image URL instead of
holding a MIME type like `image/jpeg`) and is deliberately ignored.

## Paywall behavior

None observed. Both sampled articles (an Eastern Cape politics story and a
Zambia election story) had complete, untruncated body text with no
`isAccessibleForFree` field at all.

## Known limits

- Only 2 articles sampled in depth (South African politics, Africa
  regional news). Opinion (`thought-leader`) and lifestyle (`friday`)
  sections were seen in link discovery but not verified for the same
  `<article>`/`<p>` structure.
- 404s are real HTTP 404s (verified with a synthetic slug) -- no soft-404
  behavior observed.

## Diff cadence

Quarterly smoke test recommended.
