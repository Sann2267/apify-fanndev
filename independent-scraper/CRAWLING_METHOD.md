# Crawling Method — The Independent (UK)

**Last verified:** 2026-08-24

## WAF

`independent.co.uk` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the Google News sitemap --
no challenge body, no 403.

`robots.txt` is a generic boilerplate (blocks `Nutch` outright, disallows
internal paths like `/admin/`, `/api/`, `/search/`) with **no Claude/
GPTBot/anthropic-ai disallow of any kind**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.independent.co.uk/<section>/.../<slug>-b<id>.html`

Unlike most of this portfolio, metadata and body text come from **two
different places**:

- **Metadata** from a `NewsArticle` ld+json block (`headline`,
  `description`, `author`, `datePublished`/`dateModified`,
  `isAccessibleForFree`, `image`) -- this block has **no `articleBody`
  field at all**.
- **Body text** scraped from HTML: every `<p>` tag inside the page's
  `<article>` element. The `<article>` container also holds several
  **UI boilerplate paragraphs with no distinguishing class** -- a
  login-refresh prompt, a newsletter-signup consent line, a "join the
  conversation" comments CTA, and a bookmark-removal toast -- mixed in
  with the real paragraphs at fixed positions (start/end). These are
  filtered out by **exact-prefix string match** against a short known
  list (see `BOILERPLATE_PREFIXES` in `extractor.py`). Real body
  paragraphs live inside a styled-components div with a hash class name
  (`sc-14x1gfp-0` at time of writing) -- **deliberately not used for
  selection**, since styled-component hashes rotate on every frontend
  redeploy; boilerplate-text filtering is more durable here than
  class-based selection.

`isAccessibleForFree` was `true` on all 3 sampled articles (sport, world
news, Asia) -- **no premium/metered article was found in this recon**, so
paywall truncation behavior is unverified. The field is passed through as-
is so downstream consumers can filter/flag on it if `false` values turn up
in production.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.independent.co.uk/sitemaps/googlenews`

Google News sitemap, advertised via `Sitemap:` in `robots.txt` (a second
`Sitemap: https://www.independent.co.uk/sitemap.xml` also exists but isn't
used here). Rich shape: `news:title`, `news:publication_date`,
`news:keywords` (comma-separated), `lastmod`, one `image:image` block per
entry. 364 entries present at time of writing.

**Quirk:** `image:loc` is wrapped in a `<![CDATA[...]]>` block. Entities
inside CDATA sections are **not XML-decoded** by the parser (this is
correct per the XML spec, not a bug) -- so a query-string `&` in the image
URL arrives as the literal text `&amp;` and needs one manual
`html.unescape()` pass. `title`/`link`/`keywords` were plain (non-CDATA)
text in all sampled entries and needed no such fix.

## Paywall behavior

Not directly observed -- all 3 sampled articles were fully free
(`isAccessibleForFree: true`) with complete, untruncated body text. The
Independent does have a "Premium" opinion tier in production; if a premium
article's body paragraphs turn out to be truncated or absent, the extractor
would raise `UnexpectedShape` (empty body) rather than emit a partial
record silently.

## Known limits

- Only 3 articles sampled (sport, world/Australasia, Asia/Japan). Opinion
  and premium-tagged content types are unverified.
- 404s are real HTTP 404s (verified with a synthetic URL) -- no soft-404
  behavior observed.
- The boilerplate-prefix filter is a maintenance point: if The Independent
  changes the wording of its login/newsletter/comments prompts, those
  paragraphs would leak into `articleBody` until the prefix list is
  updated. This is a deliberate trade-off vs. relying on rotating
  styled-component class hashes.

## Diff cadence

Quarterly smoke test recommended, plus a spot-check of the boilerplate
prefix list if `articleBody` output ever shows an unexpected leading/
trailing sentence.
