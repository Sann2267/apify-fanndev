# Crawling Method — Kyiv Independent

**Last verified:** 2026-08-24

## WAF

`kyivindependent.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the Google News sitemap --
no challenge body, no 403.

`robots.txt` only disallows Ghost CMS internal paths (`/ghost/`, `/p/`,
`/preview/`, `/email/`, `/members/`, `/crowdfunding/`) and tracking query
strings -- **no Claude/GPTBot/anthropic-ai disallow of any kind**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://kyivindependent.com/<slug>/`

The Kyiv Independent runs on **Ghost CMS** (confirmed via `/ghost/` admin
path in robots.txt) with a Next.js frontend. A single `NewsArticle`
ld+json block carries rich metadata (`headline`, `description`, `author`,
`datePublished`/`dateModified`, `isAccessibleForFree`, `keywords`, `image`,
`articleSection`) but **no `articleBody` field** -- body text is scraped
from HTML instead: every `<p>` tag inside the page's `<article>` element.
Unlike `independent-scraper`, **no UI boilerplate was found mixed into the
`<article>` container** in either of the 2 sampled articles (7 and 21 real
paragraphs respectively -- first and last paragraph in both cases were
genuine body text, not a login/newsletter/donation prompt) -- so no
prefix-filtering is needed here, a plain `find_all("p")` join is
sufficient.

`author` is a single `Person` object with a long `description` field
containing the reporter's full bio -- only `name` is extracted, the bio is
dropped (not article content). `keywords` arrives as a **comma-separated
string** (e.g. `"War, Ukraine, United States, Sumy Oblast, Russia, Drone
attack"`), not a JSON array -- split on `,` and stripped to normalize into
a list, matching the shape used elsewhere in this portfolio.

`isAccessibleForFree` was `true` on both sampled articles -- The Kyiv
Independent is a reader-funded nonprofit newsroom and appears to publish
all news content free of any paywall.

### 2. Latest headlines — `S2-sitemap`

`GET https://kyivindependent.com/news-sitemap.xml`

Google News sitemap, advertised via `Sitemap:` directive in `robots.txt`
(a second general `sitemap.xml` also exists but isn't used here). Standard
shape: `news:title`, `news:publication_date`, `lastmod`, one `image:image`
block per entry. 28 entries present at time of writing.

## Paywall behavior

None observed. Both sampled articles (a breaking wire-style news brief and
a longer political feature) were `isAccessibleForFree: true` with complete
body text.

## Known limits

- Only 2 articles sampled in depth (a short breaking-news brief and a
  longer political feature). If a different content type (e.g. a live
  blog, opinion piece, or investigation with an embedded paywall/member-
  only gate) behaves differently, `UnexpectedShape` will raise on missing
  `<article>`/paragraphs rather than silently returning nothing.
- 404s are real HTTP 404s (verified with a synthetic slug) -- no soft-404
  behavior observed.
- `GET /feed/` (a common Ghost RSS path) returned a Next.js 404 page, not
  RSS -- the sitemap is the only confirmed `latest`-mode source.

## Diff cadence

Quarterly smoke test recommended.
