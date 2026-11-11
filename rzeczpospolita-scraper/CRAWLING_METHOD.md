# Crawling Method — Rzeczpospolita

**Last verified:** 2026-08-24

## WAF

`rp.pl` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the Google News sitemap -- no
challenge body, no 403.

`robots.txt` disallows technical/preview paths (`*template=printart*`,
`/szukaj/*` [search], `/content/preview/*`, one specific dead article
`/przemysl-spozywczy/art39005721-*`, etc.) for `*` -- **no
Claude/GPTBot/anthropic-ai disallow of any kind.**

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.rp.pl/<section>/art<id>-<slug>`

The page emits a **single** `NewsArticle` ld+json block (no separate
`Organization`/`BreadcrumbList` blocks to filter out, unlike TASS/RT).
It carries `headline`, `description`, `keywords`, `articleSection`,
`datePublished`, `dateModified`, `isAccessibleForFree` (paywall metering
flag), `isPartOf` (subscription-tier product, e.g. `{"name":
"Rzeczpospolita - dostęp podstawowy", "productID":
"rp.pl:podstawowy"}`), `author`/`creator` (both arrays of `Person`,
identical content in the one sample checked), `publisher`, `image` --
but **no `articleBody`**.

Full text comes from `p.article--paragraph--text` (exact class match).
**Key quirk found during recon:** the article body div also contains
inline "Czytaj więcej" (read-more) related-article widget blocks, but
those use *different* classes (`subtitle` for the "Czytaj więcej" label,
`lead` for the linked article's teaser) -- so selecting the exact class
`article--paragraph--text` naturally excludes them without any extra
filtering logic. Verified: `div.articleBody` alone (without the class
filter) picks up 4 extra non-paragraph elements interleaved with the 10
real paragraphs.

**Second quirk:** the CMS's template source hard-wraps paragraph text
with literal `\n` characters mid-sentence (e.g. `"Dyrektorzy\nplacówek w
rozmowach..."`) -- this is a source-formatting artifact, not intentional
line breaks. `get_text()` alone leaves these embedded newlines in the
output untouched (they're inside a single text node, not between tags),
so every extracted paragraph is passed through a whitespace-collapse
regex (`re.sub(r"\s+", " ", text)`) before joining paragraphs with blank
lines.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.rp.pl/sitemaps/news-sitemap.xml`

Google News sitemap, advertised via `Sitemap:` in `robots.txt` (a second
`Sitemap: .../sitemaps/sitemap.xml` also exists but is the full,
non-news sitemap -- the news-specific one was used for freshness).
Standard shape: `news:title`, `news:publication_date` (ISO-8601 with
`+02:00` timezone offset). No `news:keywords` element present in this
feed (unlike Global Times' sitemap), so the `latest`-mode record omits a
keywords field entirely rather than emitting an empty list.

## Paywall behavior

**Metered paywall confirmed via `isAccessibleForFree` flag.** The one
sample verified in depth (`isAccessibleForFree: true`, tier "dostęp
podstawowy" / basic access) had full article text in the HTML matching
its ld+json description. A premium-tier sample (`isAccessibleForFree:
false`) was **not** captured during recon -- the extractor reports the
flag and subscription-tier name (`_paywalled` convenience boolean) but
does not know, and does not guess, whether premium article bodies are
truncated in the HTML the same way `isAccessibleForFree` is metered.
Treat `_paywalled: true` records as needing manual verification of body
completeness until a premium sample is checked.

## Known limits

- Only 1 article sampled in depth (a free-tier health-sector news brief,
  10 paragraphs). A premium/paywalled article, an opinion piece
  (potentially single-author `Person` instead of array), and a
  live-blog/breaking-news format were not sampled.
- 404s are real HTTP 404s (verified with a synthetic out-of-range
  article ID) -- no soft-404 behavior observed, though the 404 response
  body is a full templated page (~80KB), not a minimal error page.

## Diff cadence

Quarterly smoke test recommended; monthly if used for paywall-tier
tracking specifically (subscription product names/pricing tiers can
change without notice).
