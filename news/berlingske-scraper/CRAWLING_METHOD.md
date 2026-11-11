# Crawling Method — Berlingske

**Last verified:** 2026-08-24

## WAF

None detected. `berlingske.dk` sits behind no Cloudflare/DataDome/PerimeterX/Akamai/Fastly/Aliyun/Kasada layer that could be found:

- `curl_cffi` `chrome124` returned **200** on the homepage (577 KB), article pages, and `/news-sitemap.xml` (146 KB) with no `cf-ray`, `x-datadome-cid`, `x-kasada-tier`, `x-akamai-*` headers and no challenge-body markers.
- `robots.txt` returns 200 and disallows `GPTBot` and `CCBot` — but has **no disallow for `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai`**, checked by exact user-agent name. Respected per project policy: only Claude-specific blocks are honored as a skip signal.

**TLS profile pinned:** `chrome124`, per the portfolio-wide default of avoiding `chrome131` (most-blocklisted profile elsewhere) even though it currently also works here.

## Data sources

### 1. Article pages — `S1-nextdata` (only source, no JSON-LD fallback)

`GET https://www.berlingske.dk/<section>/<slug>`

The page carries a single `application/ld+json` block, but it's `@type: "WebSite"` (a generic site-search schema), never `NewsArticle` — unlike the rest of the portfolio, JSON-LD is a dead end here. The real data lives in `<script id="__NEXT_DATA__">` → `props.pageProps.article`: a rich block-based object with `id`, `title`, `headline`, `subheadline`, `articleType`, `categories`, `tags`, `contributions` (byline), `leadAssets`, `payWall`, `body` (a list of `ParagraphNode` blocks, each with `TextNode` children carrying the actual text), and `relatedArticles`. Passed through verbatim (raw-passthrough convention) with a flattened `articleText` convenience field added (joins all `TextNode.value` strings from `body`, paragraph-separated).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.berlingske.dk/news-sitemap.xml`

A Google News sitemap (`xmlns:news`) with `loc`/`news:title`/`news:publication_date` per `<url>` — no `news:keywords` (unlike bild.de's equivalent feed). Each `<url>` also carries an `<image:image><image:loc>` sibling tag; the extractor scopes `find("loc")` to each `<url>` element specifically (not a page-wide `find_all("loc")`) to avoid picking up those image URLs by mistake — this bit during initial recon.

## Paywall behavior

`payWall` was `None` on **all 5 live articles sampled** from the news sitemap (2026-08-24), each with a substantial body (900–1,800 extracted chars across 10–14 paragraph blocks) — no paywalled sample was found during recon. The extractor still sets `_paywalled: true` whenever `payWall` is truthy (not `None`/`False`) for any URL a user supplies directly, but the exact shape of a paywalled `payWall` value (boolean vs. dict) has not been empirically observed — treat this as best-effort until a real sample turns up.

## Known limits

- Paywall handling (`_paywalled` flag) is implemented defensively from the `payWall` field but not empirically confirmed against a live paywalled article — none turned up in the 5-article sample.
- `latest` mode returns whatever is currently in `/news-sitemap.xml` at fetch time; no historical/pagination parameter exists for this feed.
- Article extraction depends entirely on `__NEXT_DATA__` (no JSON-LD fallback exists on this site) — if Berlingske migrates off this Next.js data container, extraction fails loudly (`UnexpectedShape`) rather than silently degrading, per project convention.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh sitemap entry and confirm `__NEXT_DATA__.props.pageProps.article` still resolves with `body`/`title` keys present. If Berlingske redesigns, this will raise `UnexpectedShape` and fail the run loudly rather than emit corrupt records.
