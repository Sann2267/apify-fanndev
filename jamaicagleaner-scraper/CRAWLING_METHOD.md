# Crawling Method — Jamaica Gleaner

**Last verified:** 2026-08-25

## WAF

`jamaica-gleaner.com` shows **no active WAF challenge**. `curl_cffi`
`chrome124` gets a clean 200 on the homepage and article pages.
`robots.txt` is a standard Drupal-generated file (disallows only
`/admin/`, `/core/`, `/profiles/`, `/user/register`, `/search/`, `/node/
add/`, `/comment/reply/` -- CMS system paths), no Claude/GPTBot/
anthropic-ai disallow of any kind.

**Reliability quirk (not a block):** the backend intermittently returns
`ConnectionError: Empty reply from server` (curl error 52) instead of a
normal HTTP response -- confirmed genuinely transient by retrying the
exact same URL seconds later and getting a clean response (observed both
patterns: 2 successes then 1 failure, and 6 consecutive successes, on the
identical URL in the same session). This is real backend flakiness, not
a deterministic anti-scraping measure targeting any particular URL shape
-- it happens on both real articles and nonexistent ones. The existing
`except Exception` catch-all in `client.py`'s retry loop already handles
this (a `ConnectionError` is retried with backoff exactly like a 503
would be) -- no special-casing needed, but a batch run against many URLs
may occasionally need the full retry budget on a handful of them.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Why this was previously flagged as hard (and how it was resolved)

Prior recon (Babak 11) found `sitemap.xml` pointing at an internal IP and
`rss.xml` returning an empty stub, and left this site unbuilt pending "an
alternative discovery strategy." This pass confirmed both are still
broken and used homepage-link scraping instead (see below) -- the same
fallback strategy already proven on `chinadaily-scraper` and
`globaltimes-scraper` when a site's official feed/sitemap is unusable.

## Data sources

### 1. Article pages — `S1-html`

`GET https://jamaica-gleaner.com/article/<section>/<YYYYMMDD>/<slug>`

The page emits a single ld+json block typed `Article` with `headline`,
`image`, `datePublished`, `dateModified`, and `isAccessibleForFree` --
but no `articleBody`, `description`, or `author`. Full text comes from
HTML `div.article--body > p` -- confirmed clean on 2 samples (business,
commentary/opinion sections), no ad/related-article junk paragraphs mixed
in. The last paragraph is sometimes a reporter's byline email (e.g.
`"neville.graham@gleanerjm.com"`) -- left in as real editorial content per
raw-passthrough convention, not stripped, since there's no reliable way
to distinguish "byline email" from "a paragraph that happens to end in an
email address" without an allow-list of known reporter emails (out of
scope).

`postedDate` (a readable but non-ISO string like `"August 23 2026"`) is
pulled separately from `.article--posted-date` as a secondary field
alongside the ld+json `datePublished`, which is a proper ISO timestamp and
should be preferred by consumers that need to parse a date programmatically.

Both sampled articles had `isAccessibleForFree: true`; the `_paywalled`
output flag is still derived defensively from the real field.

### 2. Latest headlines — `S2-html-listing`

`GET https://jamaica-gleaner.com/` (homepage)

`sitemap.xml` returns HTTP 404. `rss.xml` returns HTTP 200 but is a
genuinely empty stub -- `<channel>` with a `<title>`/`<link>` but **zero**
`<item>` elements (confirmed on this pass, matching the prior session's
finding).

Instead the homepage is scraped for `<a href>` links matching
`/article/<section>/<YYYYMMDD>/<slug>`. Because the date is embedded
directly in the URL path, sorting the found links descending by that date
component reproduces newest-first order without visiting each article
page. Each link can appear multiple times in the markup (thumbnail link,
headline link, teaser link) -- the extractor keeps the longest non-empty
anchor text seen for a given URL as the title, same pattern as
`chinadaily-scraper`.

## Paywall behavior

None observed as a hard gate. `isAccessibleForFree: true` on both sampled
articles.

## Known limits

- Only 2 articles sampled in depth (business, commentary/opinion). A
  structurally different page type (live-blog, photo gallery, video) was
  not sampled and might lack `div.article--body` entirely -- would raise
  `UnexpectedShape` rather than silently emit a wrong or empty record.
- `urlDate` in `latest` mode is day-precision only (derived from the URL
  path) -- fetch the article (`article` mode) for the exact
  `datePublished` from its ld+json block.
- Intermittent `ConnectionError: Empty reply from server` on the backend
  (see WAF section) -- handled by retry, but not eliminated; a very
  unlucky run could still exhaust retries on a URL that would have
  succeeded on a 6th attempt.

## Diff cadence

Quarterly smoke test recommended.
