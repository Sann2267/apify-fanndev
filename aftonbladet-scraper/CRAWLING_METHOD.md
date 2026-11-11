# Crawling Method — Aftonbladet

**Last verified:** 2026-08-24

## WAF

None detected. `aftonbladet.se` sits behind no Cloudflare/DataDome/PerimeterX/Akamai/Fastly/Aliyun/Kasada layer that could be found:

- `curl_cffi` `chrome124` returned **200** on the homepage (489 KB), article pages, and `/rss.xml` with no `cf-ray`, `x-datadome-cid`, `x-kasada-tier`, `x-akamai-*` headers and no challenge-body markers.
- `robots.txt` returns 200 and has **no `Disallow` for any AI-bot user-agent** (`Claude`, `ClaudeBot`, `Claude-Web`, `anthropic-ai`, `GPTBot`, `CCBot`, `bytespider`, `Google-Extended` all checked by name — none blocked).

**TLS profile pinned:** `chrome124`, per the portfolio-wide default of avoiding `chrome131` (most-blocklisted profile elsewhere) even though it currently also works here.

## Data sources

### 1. Article pages — `S1-jsonld` (primary)

`GET https://www.aftonbladet.se/<section>/a/<id>/<slug>`

The page emits **two separate** `<script type="application/ld+json">` tags — one `BreadcrumbList`, one `NewsArticle` — unlike bild.de's single list-wrapped block. The extractor scans all ld+json tags on the page and picks the dict with `@type == "NewsArticle"`. That block carries `headline`, `datePublished`/`dateModified`, `wordCount`, `articleSection`, `description`, `keywords`, `image`, `isAccessibleForFree`, `publisher`, `author` — but **no `articleBody`**. Full text is pulled separately from the rendered HTML: `main article` container, all `<p>` tags joined with a blank line.

Verified against `wordCount` on 10 live articles sampled from `/rss.xml` (2026-08-24): extracted paragraph text consistently scales with `wordCount` (e.g. `wordCount: 70` → 746 extracted chars; `wordCount: 642` → 4,442 extracted chars) with no sign of truncation.

### 2. Latest headlines — `S2-rss`

`GET https://www.aftonbladet.se/rss.xml`

Standard RSS 2.0, confirmed live with `title`/`link`/`pubDate`/`description` per `<item>` — no body text. `/sitemap.xml` also exists but is a sitemap **index** (dated sub-sitemaps like `/sitemaps/1994-07-articles.xml`), more awkward to consume than the flat RSS feed for a "latest N" use case, so RSS was chosen as primary.

## Paywall behavior

Aftonbladet has a premium tier ("Aftonbladet Plus"), but **none of the 10 live articles sampled from `/rss.xml`** (2026-08-24) were paywalled — all had `isAccessibleForFree: true` with full-text bodies. The RSS feed appears to only surface free articles. The extractor still checks `isAccessibleForFree` on every article-mode request (sets `_paywalled: true` when it's explicitly `false`) since a user-supplied URL could point directly at Plus content that never appears in the feed — this just wasn't observed during recon, unlike bild.de where paywalled samples were directly confirmed.

## Known limits

- Paywall behavior for "Aftonbladet Plus" content is implemented defensively (flag set from `isAccessibleForFree`) but not empirically confirmed against a live Plus article — none turned up in the RSS sample. Revisit if a `_paywalled: true` record with a suspiciously long `articleBody` shows up (would indicate the flag logic needs adjustment).
- `latest` mode returns whatever is currently in `/rss.xml` at fetch time; no historical/pagination parameter exists for this feed.
- Article body extraction uses an HTML container selector (`main article`), not JSON — if Aftonbladet redesigns the page template this degrades to `None` rather than raising, since the ld+json block (headline/author/dates/etc.) is still valid and shouldn't be thrown away over a missing body.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh RSS entry and confirm `main article` still returns non-empty `<p>` text and its length still tracks the ld+json `wordCount` field. If Aftonbladet changes templates, `articleBody` will silently go `null` — that's the trigger to re-inspect the selector, not a crash.
