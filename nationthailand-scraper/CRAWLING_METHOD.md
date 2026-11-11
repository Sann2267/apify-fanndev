# Crawling Method — The Nation Thailand

**Last verified:** 2026-08-25

## WAF

`nationthailand.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on the homepage, article pages, and the sitemap -- no
challenge body, no 403.

`robots.txt` has a simple `User-agent: * / Disallow: /search, /*.php,
/*.htm*` group, no Claude/GPTBot/anthropic-ai disallow of any kind. It
advertises `Sitemap: https://www.nationthailand.com/sitemap/latest` (used
for `latest` mode), a full site index, and a tag sitemap.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.nationthailand.com/news/<section>/<id>`

The page emits 5 ld+json blocks (2x `Organization`, `WebSite`,
`BreadcrumbList`, and the `NewsArticle` itself) -- the extractor scans all
blocks and picks the one whose `@type` is `NewsArticle`. It carries
`headline`, `description`, `keywords`, `articleSection`,
`dateCreated`/`datePublished`/`dateModified`, `author`, `publisher`,
`image`, and `isAccessibleForFree` -- and it **does** have an
`articleBody` key, but that field is just the short deck/teaser
(confirmed identical to `description`, ~140-150 chars on both sampled
articles), **not** the full article. Full text is pulled separately from
HTML `div.content-detail > p` instead.

**Soft-404 quirk:** a nonexistent article ID returns HTTP 200 rendering
the homepage shell (identical byte length to a real homepage fetch, no
distinct error page, no real 404 status). Detected via `<link
rel="canonical">`: on a real article it matches the requested URL exactly;
on the soft-404 shell it always points at the bare homepage
(`https://www.nationthailand.com/`) instead -- a mismatch raises
`SoftNotFound`, which `main.py` converts into a clean `_error: "not_found"`
diagnostic row (same output shape as a genuine HTTP 404 would produce).

No hard paywall marker was found -- `isAccessibleForFree` was `True` on
both sampled articles; the `_paywalled` output flag is still derived
defensively from the real field.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.nationthailand.com/sitemap/latest`

A Google News-flavored XML sitemap. Most `<url>` entries in this sitemap
are actually category/tag landing pages (`/category/business`, etc.) with
no `<news:news>` block -- confirmed 5 of the first ~10 entries are
non-article pages. Only entries that DO carry a `<news:news>` block
(with `news:title` and `news:publication_date`) are treated as real
articles; everything else is skipped. Document order is already
newest-first.

## Paywall behavior

None observed as a hard gate. `isAccessibleForFree: true` on both sampled
articles.

## Known limits

- Only 2 articles sampled in depth (both `news/world` and `news/general`
  sections). A structurally different page type (live-blog, photo
  gallery, opinion) was not sampled and may use a different body
  container or lack `isAccessibleForFree` -- these would raise
  `UnexpectedShape` rather than silently emit a wrong or empty record.
- `articleBody` in the raw ld+json is a teaser, not the full text -- do
  not "simplify" the extractor to read it directly without re-verifying
  this is still true.
- The sitemap mixes category/tag pages with real articles in the same
  feed -- filtering on the presence of `<news:news>` is required, not
  optional.

## Diff cadence

Quarterly smoke test recommended.
