# Crawling Method — Deccan Chronicle

**Last verified:** 2026-08-26

## robots.txt

Independently re-fetched and re-verified (`curl_cffi` `chrome124`) before any
code was written, per the standing "Babak 14" incident requirement:

- `https://www.deccanchronicle.com/robots.txt` and the bare `deccanchronicle.com`
  host both return 200 with identical content.
- `User-agent: *` carries `Allow: /` plus a set of narrow `Disallow:` rules
  (`/admin/`, `/xhr/`, `/staging/`, `/search/`, query-string crawl traps like
  `?page=`/`?sort=`, `/preview/story-`, `/embed/`, a handful of internal paths,
  and font files) — no blanket `Disallow: /`.
- `User-agent: Googlebot-News` is explicitly granted `Allow: /`.
- **No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-SearchBot`, or
  `anthropic-ai` user-agent block anywhere in the file.**
- Three sitemaps declared: `news-sitemap-daily.xml`, `sitemap-daily.xml`,
  `sitemap-daily-updated.xml`.

Verdict: clear to build.

## WAF

None detected. `curl_cffi` `chrome124` returned 200 on the homepage, three
sampled article pages, `/robots.txt`, `/rss.xml`, and `/news-sitemap-daily.xml`
— no `cf-ray`, no `x-datadome`, no `_abck`/PerimeterX cookies, no challenge
body, no 403/429. Response headers show `server: nginx/1.24.0` behind
CloudFront (`x-cache: Miss from cloudfront`, `via: ... cloudfront.net`) — a
CDN, not a bot-management WAF.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.deccanchronicle.com/<section>[/<subsection>]/<slug>-<id>`

Each article page emits 5 separate `application/ld+json` blocks
(`Organization`, `WebPage`, `BreadcrumbList`, `NewsArticle`, `ItemList`
site-nav) — the extractor picks the `NewsArticle` one specifically. It
carries `articleBody` with the **full plain-text article** (1,300–4,300
characters across 3 samples), `headline`, `alternativeHeadline` (identical to
`headline` on all samples), `description`, `keywords` (comma-separated
string, not an array), `about` (array of `Thing` topic tags), `articleSection`
/ `genre` (both mirror the section name), `author` (array of `Person`, name
is either a named byline like "DC Correspondent" or a wire-service credit
like "PTI"/"AFP"/"AP"/"ANI"), `image`, and `datePublished`/`dateModified`
(ISO 8601 with `+05:30` IST offset).

**Quirk — literal control character in `articleBody`:** on a live sample
(`canada-unveils-counter-tariffs-of-1550-on-us-goods-1982343`), the
`articleBody` string contained a **literal, unescaped tab character**
(`\t`) rather than the JSON-mandated `\t` escape sequence. This is invalid
per strict JSON (RFC 8259 requires control characters to be escaped), so
Python's `json.loads()` with its default `strict=True` raises
`JSONDecodeError: Invalid control character`. The extractor
(`src/extractor.py::_parse_ld_json`) retries with `strict=False` on that
specific failure, which accepts literal control characters in strings. This
is a genuine upstream CMS quirk (not sample-specific mojibake — confirmed by
inspecting the raw response bytes), so every article fetch goes through this
tolerant-parse path rather than a one-off patch.

**Not a quirk (ruled out):** `El Ni�o` / `15�50%`-looking characters seen in
raw terminal output during recon were a **Windows console rendering
artifact**, not a data problem — raw byte inspection confirmed correct UTF-8
encoding (`0xC3 0xB1` for "ñ", `0xE2 0x80 0x93` for the en-dash). No
`html.unescape()` pass is needed; `articleBody`/`title`/`description` were
checked for `&amp;`/`&#39;`/`&quot;`/`&rsquo;`/`&ndash;` entities on 3 samples
and none were found.

No `isAccessibleForFree`/`hasPart` paywall-signal fields were observed on any
sampled article. No `__NEXT_DATA__` was found — this site does not expose
page state via Next.js SSR data injection; it's a traditional server-rendered
CMS page.

### 2. Latest headlines — `S2-rss`

`GET https://www.deccanchronicle.com/rss.xml`

This resolves to the same feed the site's own `<atom:link rel="self">`
declares as `https://www.deccanchronicle.com/google_feeds.xml`. Standard RSS
2.0 (`<channel>/<item>`), fields: `title`, `link`, `guid`, `pubDate`,
`description`, `category` (comma-joined when an item has multiple, e.g.
`"Southern States,Telangana,Home Highlight"`), `dc:creator` (byline/wire
credit), and `content:encoded` (full article HTML — a lead-image `<figure>`
plus `<p>` paragraphs, same text as `articleBody` on the article page).

Unlike Hindustan Times in this portfolio (which only exposes per-section RSS
feeds), this is a **single site-wide feed** covering all sections — no
section parameter needed for full latest-mode coverage. Confirmed live and
chronological on 2026-08-26: `lastBuildDate` matched wall-clock time and the
newest item was ~1 minute old at fetch time.

A `/feed/` path also exists (200, `application/rss+xml`, ~2.3MB) but appears
to be a much larger/older combined feed; `/rss.xml` (~210KB, same content
freshness) was used instead since it matches the site's own declared
canonical feed URL and is far cheaper to fetch per run.

## Paywall behavior

No paywall markers, truncation, or subscriber-only gating observed on any
sampled article. Deccan Chronicle appears to be a fully free, ad-supported
site.

## Known limits

- `keywords` is a comma-separated string in the JSON-LD, not an array like
  most other outlets in this portfolio — passed through as-is, not split.
- `articleSection`/`genre` are both present and identical on every sample —
  redundant but both passed through raw.
- `category` in latest-mode RSS items can be a comma-joined multi-value
  string (e.g. `"World,America"`) rather than a single tag — passed through
  as-is.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`, and that the `strict=False` JSON-LD fallback path is still
needed (or still sufficient) if the control-character quirk persists. If
Deccan Chronicle redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
