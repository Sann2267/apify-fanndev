# Crawling Method — Mmegi (Botswana)

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh (not reused from the orchestrator's fast screen) as the mandatory first
step. `mmegi.bw/robots.txt` (176 bytes, HTTP 200) has three `User-agent` groups:

```
User-agent: MJ12bot
Disallow: /*

User-agent: PetalBot
Disallow: /

User-agent: *
Disallow: /ajax/*
Disallow: /*.pdf
Disallow: /widget/*
Disallow: */page/*
Disallow: /search*
```

The `User-agent: *` group (the one that applies to this actor) has NO blanket
`Disallow: /` — only `/ajax/*`, `/*.pdf`, `/widget/*`, `*/page/*`, `/search*` are
disallowed, none of which this actor touches (article pages and `/rssFeed/<id>` are
both allowed). No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` token appears anywhere in the file — the
MJ12bot/PetalBot blocks are scoped to those specific bots only and don't apply here.
There is no `sitemap:` line in this file at all.

## WAF

`mmegi.bw` sits behind a layered CDN — Cloudflare at the edge (`server: cloudflare`,
`cf-ray`, `cf-cache-status`) fronting an AWS CloudFront/ALB origin (`X-Cache: ...
cloudfront`, `Via: ... cloudfront.net`, `AWSALB`/`AWSALBCORS` cookies) — but shows
**no active bot-management challenge**. `curl_cffi` `chrome124` gets a clean 200 on
the homepage, every sampled article page (3 sections: news, sports,
opinion-amp-analysis), the `/rss` sitemap page, and all sampled `/rssFeed/<id>`
feeds — on the first try, no profile-ladder escalation needed. No `cf_clearance`
cookie, no `__cf_chl_*`, no "Just a moment..." interstitial, no CAPTCHA. The
`AWSALB`/`AWSALBCORS` cookies are plain load-balancer session stickiness, not a
challenge token.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.mmegi.bw/<section>/<slug>/news`

All 3 sampled sections (`news`, `sports`, `opinion-amp-analysis`) emit exactly ONE
top-level `NewsArticle` ld+json node (no `@graph` wrapper) that carries
**`articleBody` with the full article text inline** — no HTML scraping needed. Also
present: `headline`, `description`, `keywords` (a comma-separated string —
**observed to just be the headline's own words re-joined with commas**, e.g.
`"South,Africa,builds,Africa's,healthcare,supply,chains,as,USD,2,billion,flows,into,the,sector"`
for a headline of the same words — not real topical tags; kept as a split list
anyway, raw passthrough style), `inLanguage` (`"en-US"`), `thumbnailUrl`, `image` (a
**single `ImageObject` dict**, not a list — differs from `standardmedia-scraper`
where `image` is a list), `author` (a **single `Person` dict**, not a list —
observed values: generic `"correspondent"` / `"staff writer"` for wire-style/staff
pieces, and real individual names, e.g. `"REALEBOGA PHOI"`, `"Larona Makhaiza"`, on
byline-attributed pieces), `publisher` and `copyrightHolder` (both `Organization`
dicts with `name`/`url`/`sameAs`/`logo`), `dateCreated`/`datePublished`/
`dateModified` (ISO 8601 with `+02:00` offset), and `mainEntityOfPage` (`{"@type":
"WebPage", "@id": <canonical url>}`, used as `canonicalUrl` — identical to the input
URL in all 3 samples, no redirect/canonicalization quirk found).

**No paywall metadata was found anywhere** — no `isAccessibleForFree`, no `hasPart`
— unlike `standardmedia-scraper`'s Piano-style flags. Mmegi's online articles appear
fully open; no login/subscription wall was ever encountered while sampling across 3
sections.

**Key quirk — single HTML-entity escaping.** `articleBody` (and RSS `title`/
`description`, see S2 below) is single html-entity-escaped on the wire — e.g. a
literal double-quote character in the source content is served as the literal
4-character sequence `&quot;` inside the JSON string value (confirmed on raw
response bytes: `\xe2\x80\x99` for a real UTF-8 right-single-quote character
alongside literal `&quot;` for double-quotes in the same body — i.e. genuine mixed
encoding, not a decoding artifact). One `html.unescape()` pass recovers the real
character; verified `html.unescape(html.unescape(x)) == html.unescape(x)` on a
sampled body (idempotent), so `_clean_text()` in `extractor.py` applies it once and
is safe to reuse on every text field. **Unlike `standardmedia-scraper`, this is NOT
double-escaped** — a single pass is enough, and there is no need for the
`html.unescape()` × 2 pattern used there.

Standard-library `json.loads()` in **strict mode** (no `strict=False` needed)
parses every one of the 3 sampled `NewsArticle` blocks cleanly — no stray
unescaped control characters (`\r`/`\n` inside string values) were found on the
wire here, unlike `standardmedia.co.ke`'s confirmed quirk.

### 2. Latest headlines — `S2-rss`

`GET https://www.mmegi.bw/rssFeed/1` (News category)

Mmegi runs **per-category RSS feeds** at `/rssFeed/<id>`, discovered via the
human-readable `/rss` page (titled "Sitemap" in the site's own footer link, but is
actually an HTML index of RSS feed links, NOT a machine-readable XML sitemap —
this site has no `sitemap:` line in `robots.txt` at all). Category IDs observed:
News=1, Business=2, Sports=3, Features=4, Opinion & Analysis=13 (with sub-feeds
Editorial=13/23, Blogs=13/24, Columns=13/25), Blogs=24 (with ~18 named columnist
sub-feeds), Lifestyle=25, and more. This actor uses **News (id=1)** as the single
`latest`-mode source, matching the portfolio's single-feed convention (see
`mailguardian-scraper`/`thecitizen-scraper` precedent).

Standard RSS 2.0 shape, every field CDATA-wrapped: `<title>`, `<link>`,
`<description>` (a short teaser, same single-escaping quirk as `articleBody` —
`_clean_text()` is reused), `<author>` (a plain name string, not an RFC-2822 email
— identical values to the ld+json `author.name`, e.g. `"correspondent"`,
`"staff writer"`, `"Larona Makhaiza"`), `<pubDate>` (RFC-822), plus
`<media:thumbnail>`/`<media:content>` (both carry the **same image URL** at
different declared sizes — thumbnail 400×280, content 800×557 in every sample — no
CMS bug like `mailguardian-scraper`'s duplicated-`type`-attribute quirk, both
elements are clean `url`/`width`/`height` attributes). No `<guid>` or `<category>`
element is present on this feed. 50 items returned per fetch, no pagination
offered or needed for `latest` mode.

**bs4 parser gotcha (self-inflicted during recon, noted for the next agent):** `bs4`
with the `"xml"` feature (`lxml-xml` under the hood) throws a hard parse error
(`Start tag expected, '<' not found`) if given `curl -i` output (headers + body
concatenated) — always fetch the feed body only (`curl -s` / `client.content`
without response headers mixed in) before parsing.

## Not-found behavior

A syntactically well-formed but nonexistent slug returns a genuine **HTTP 404**
(`<title>Mmegi | ERROR 404</title>`, 319KB error page) — no soft-404
redirect-to-homepage pattern like `standardmedia-scraper`. `main.py` / `test_local.py`
map this directly to `_error: "not_found"` off the status code alone.

## Known limits

- `keywords` is not a real topical-tag field — see the quirk note above. Kept for
  raw-passthrough completeness but downstream consumers shouldn't treat it as
  curated metadata.
- Only 3 sections were sampled (`news`, `sports`, `opinion-amp-analysis`). A
  structurally different template (photo gallery, live blog, or the many named
  columnist sub-sections under Blogs id=24) was not exhaustively checked and might
  lack `articleBody` in ld+json — this would currently raise `UnexpectedShape`
  rather than silently degrade, per this portfolio's fail-loud convention. No S2
  HTML-scraping fallback was implemented since no section needing one was found in
  the sample.
- Only the News category feed (`/rssFeed/1`) is used for `latest` mode; Business/
  Sports/Features/Opinion feeds exist as separate `/rssFeed/<id>` endpoints but
  aren't independently wired into this actor's input (would require adding a
  category-selector input field as a future enhancement).

## Diff cadence

Quarterly smoke test recommended.
