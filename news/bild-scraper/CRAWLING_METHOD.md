# Crawling Method — BILD

**Last verified:** 2026-08-24

## WAF

None detected. `bild.de` sits behind no Cloudflare/DataDome/PerimeterX/Akamai/Fastly/Aliyun/Kasada layer that could be found:

- `curl_cffi` `chrome124` returned **200** on the homepage (782 KB), article pages, and `/sitemap-news.xml` (305 KB) with no `cf-ray`, `x-datadome-cid`, `x-kasada-tier`, `x-akamai-*` headers and no challenge-body markers.
- `robots.txt` returns 200 and has **no `Disallow` for any AI-bot user-agent** (`Claude`, `ClaudeBot`, `Claude-Web`, `anthropic-ai`, `GPTBot`, `CCBot`, `bytespider`, `Google-Extended` all checked by name — none blocked).

**TLS profile pinned:** `chrome124`, per the portfolio-wide default of avoiding `chrome131` (most-blocklisted profile elsewhere) even though it currently also works here.

## Data sources

### 1. Article pages — `S1-jsonld` (primary)

`GET https://www.bild.de/<section>/<slug>-<id>`

The page emits one `<script type="application/ld+json">` block containing a JSON **list** of `[NewsArticle, BreadcrumbList]` — unlike most of the portfolio, which emits a single dict. The `NewsArticle` entry carries `headline`, `description`, `datePublished`/`dateModified`, `author` (array, with `jobTitle`/`sameAs`/`image`), `keywords`, `isAccessibleForFree`, `publisher`, `image` — but **no `articleBody`**. Full text is pulled separately from the rendered HTML: `div.article-body` (falls back to `article` if that container is absent), paragraphs joined with a blank line. Confirmed against `wordCount`-style sanity checks — see Paywall behavior below.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.bild.de/sitemap-news.xml`

A standard Google News sitemap (`xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"`), confirmed **reverse-chronological** (newest first) with a fresh timestamp on every fetch during recon. Each `<url>` entry carries `loc`, `news:title`, `news:publication_date`, `news:keywords` — no body text, no author. No page-count cap was found in testing (305 KB / several hundred URLs per fetch); the actor slices to the requested `limit`.

## Paywall behavior

BILD enforces a genuine (not cosmetic) "BILDplus" paywall on a subset of articles. Sampled 12 live articles from the sitemap (2026-08-24):

| `isAccessibleForFree` | `div.article-body` text length |
|---|---|
| `true` (9/12 sampled) | 1,879 – 4,752 chars (full article) |
| `false` (3/12 sampled) | 407 – 657 chars (teaser only) |

This extractor never fabricates missing text — it records whatever `div.article-body` actually serves and sets `_paywalled: true` when `isAccessibleForFree` is `false`. One sampled article had `isAccessibleForFree: null` (short/wire-brief style piece); `_paywalled` is `false` in that case (only an explicit `false` sets it `true`), matching the "don't invent state" convention.

## Known limits

- `articleBody` for paywalled (`isAccessibleForFree: false`) articles is teaser-only (a few hundred characters), by design — see Paywall behavior above.
- `latest` mode returns whatever is currently in `/sitemap-news.xml` at fetch time (typically several hundred URLs spanning ~24h); no historical/pagination parameter exists for this feed.
- Article body extraction uses an HTML container selector (`div.article-body`), not JSON — if BILD redesigns the page template this degrades to `None` rather than raising, since the ld+json block (headline/author/dates/etc.) is still valid and shouldn't be thrown away over a missing body. Watch for `articleBody: null` on otherwise-`isAccessibleForFree: true` records as the signal to re-check the selector.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh sitemap entry and confirm `div.article-body` still returns non-empty text for a free (`isAccessibleForFree: true`) article. If BILD changes templates, `articleBody` will silently go `null` (see Known limits) — that's the trigger to re-inspect the selector, not a crash.
