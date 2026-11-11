# Crawling Method — The Fiji Times

**Last verified:** 2026-08-26

## WAF

`fijitimes.com.fj` (served as `www.fijitimes.com.fj`) shows **no active
WAF challenge**. The site is Apache (Amazon Linux) fronted by CloudFront
(`x-cache`/`x-amz-cf-*` response headers, `Server: Apache/2.4.68`) — CDN
only, no `_abck`/`bm_sz`/`_px3`/`_dd_s` bot-manager cookie, no `cf-ray`,
no challenge body. Plain `curl_cffi` `chrome124` gets a clean 200 on the
homepage, article pages, `robots.txt`, and the sitemap on the very first
try — no warmup-then-retry dance actually needed in practice, though the
portfolio-standard warmup-then-retry scaffolding is kept in `client.py`
as cheap insurance.

`robots.txt` (re-verified live on 2026-08-26) is a 10-line stock Yoast
SEO block:

```
# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:



Sitemap: https://www.fijitimes.com.fj/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

Single `User-agent: *` group, `Disallow:` empty (allow-all). No
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
token anywhere, and no plain-English prohibition against AI/LLM training
or scraping in any comment — the whole file is just the Yoast boilerplate
plus a `Sitemap:` line.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.fijitimes.com.fj/<slug>/`

WordPress (Gutenberg/full-site-editing theme) + Yoast SEO v28.2, but —
unusually for a Yoast install — article pages emit **zero** ld+json: no
`<script type="application/ld+json">` block, no `__NEXT_DATA__`, no
`schema.org` reference anywhere in the page source (confirmed on all 3
sampled articles). `extract_article` is pure HTML + `<meta>` tags. The
`/wp-json/wp/v2/posts` REST endpoint is blocked (`401 rest_forbidden`),
so there's no JSON API shortcut either.

Fields:
- **Headline** — `h1.fijitimes_title`.
- **Body** — `div.entry-content.post_content > p` paragraphs, joined with
  blank lines. Confirmed clean on 3 samples, no ad/related-article junk
  mixed in.
- **Author** — `meta[name="author"]` (e.g. `"ANISH CHAND"`).
- **Description** — `meta[name="description"]`.
- **Categories** — `a[rel="category tag"]` links (e.g.
  `["Local News", "News"]`, or `["News", "Today's Main Story"]` on the
  homepage lead story).
- **datePublished/dateModified** — `meta[property="article:published_time"]`
  / `meta[property="article:modified_time"]`.
- **Image** — `meta[property="og:image"]`.

**Duplicate meta-tag quirk (not a data conflict):** each article page
emits the standard OpenGraph/Twitter/article meta tags **twice**, from
two different injection points — a Yoast-labeled block (wrapped in an
explicit `<!-- This site is optimized with the Yoast SEO plugin ... -->`
HTML comment) using the bare `fijitimes.com` domain (no `.fj`) in
`og:url` and a `" - The Fiji Times"` suffix on `og:title`/`<title>`,
followed immediately by an unlabeled duplicate block using the canonical
`fijitimes.com.fj` domain (matching `<link rel="canonical">`) and no
title suffix. Both blocks' `article:published_time` represent the
literal same instant in different notations (e.g. `06:20:13+00:00` UTC
vs `18:20:13+12:00` Fiji local — 6+12=18, consistent). `extract_article`
uses `soup.find` (first occurrence), which resolves to the Yoast-labeled
block — a deliberate, arbitrary-but-consistent choice since both blocks
carry identical values for every field checked.

No paywall of any kind was found — only a normal print-subscription nav
link (`/subscribe/`); full article text is served in the initial HTML
response with no metering/truncation observed on any of the 3 articles
sampled.

Nonexistent article slugs return a **real HTTP 404** (confirmed live on
2026-08-26 with a deliberately-invented slug) — no soft-404 quirk.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.fijitimes.com.fj/sitemap_index.xml`

The WordPress default feed (`/feed/`) 301-redirects straight to the
homepage (a dead/disabled feed, matching this portfolio's prior
experience with other smaller Commonwealth regional dailies — Jamaica
Gleaner, Trinidad Guardian). `latest` mode instead reads the Yoast SEO
`sitemap_index.xml` and picks the newest `post-sitemap*.xml` page.

Each `post-sitemap*.xml` page (1000 `<url>` entries per full page, ~260
on the newest/partial one at time of writing) is in **ascending**
chronological order by `<lastmod>` (oldest entry first, newest last) —
confirmed live across all 5 pages, whose date ranges chain into one
continuous ascending timeline (`post-sitemap.xml`: May25–Jun16 → `...2`:
Jun16–Jul05 → `...3`: Jul05–Jul27 → `...4`: Jul27–Aug20 → `...5`:
Aug20–Aug26, the current newest page), and the last entry of the newest
page matches the live homepage's current top story
(`nfp-demands-action-on-crime`).

**Newest-page-selection quirk:** the unnumbered `post-sitemap.xml`
(page 1) has a spurious first `<url>` entry for the bare homepage itself
(not an article) whose own `<lastmod>` happens to tie with the true-newest
page's — sorting `sitemap_index.xml` entries by their own `<lastmod>`
breaks on that tie. `extract_sitemap_index` instead takes the **last**
`post-sitemap*.xml` entry in the index's document order (Yoast lists
pages in ascending page order), and `extract_sitemap_items` defensively
skips any entry whose `<loc>` is just the bare homepage, on every page.

No `<title>` or per-item publish date is carried in this generic
post-sitemap (only `loc`/`lastmod`/`image:loc`) — unlike a Yoast *News*
SEO sitemap, this site does not have that plugin installed, so
latest-mode records carry only `link`/`lastmod`/`image`, not a headline.
Consumers who need the title/full metadata should fetch the article in
`article` mode.

Live re-verification (2026-08-26): `sitemap_index.xml` → newest page
`post-sitemap5.xml` → top 5 items after reversal matched the live
homepage's 5 newest stories in order, `lastmod` values descending from
`06:20:13Z` down to `02:53:23Z` the same day.

## Paywall behavior

None observed. Only a cosmetic `/subscribe/` nav link for the print
edition; full text served in the initial HTML on all 3 sampled articles.

## Known limits

- Only 3 articles sampled in depth (2 news stories + the homepage lead
  story used during recon). A structurally different page type
  (live-blog, photo gallery, video, classifieds/"Situation Vacant"
  listing) was not sampled and might lack `h1.fijitimes_title` or
  `div.entry-content.post_content` entirely — would raise
  `UnexpectedShape` rather than silently emit a wrong or empty record.
- `latest` mode's `lastmod` is a sitemap-level last-modified timestamp,
  not a guaranteed original publish time (though on every article
  checked it exactly matched `article:published_time`/`article:modified_time`
  since none had been edited post-publish). Fetch the article in
  `article` mode for the authoritative `datePublished`.
- `/wp-json/wp/v2/posts` REST endpoint returns `401 rest_forbidden` —
  no JSON API shortcut available; confirmed via a raw `curl_cffi` GET
  during recon.
- No transient `ConnectionError`/503 flakiness was observed against
  `fijitimes.com.fj` during this recon or verification session (unlike
  Jamaica Gleaner's confirmed intermittent empty-reply issue) — the
  retry scaffolding in `client.py` is kept per portfolio convention as
  cheap insurance, not because a specific failure mode was reproduced
  here.

## Diff cadence

Quarterly smoke test recommended.
