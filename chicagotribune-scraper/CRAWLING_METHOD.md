# Crawling Method — Chicago Tribune

**Last verified:** 2026-08-24

## WAF

Split behavior, unusual for this portfolio:

- **Homepage and article pages: no WAF.** `curl_cffi` `chrome124` gets a
  clean 200 with full content, no challenge body, no `cf-ray`/`x-datadome`
  markers.
- **`/feed/` (any section variant) and dated sitemap URLs
  (`/sitemap.xml?yyyy=...&mm=...&dd=...`) are gated** by a custom
  JavaScript **hashcash proof-of-work challenge**: the response is a 403
  HTML page with an inline script that computes a SHA-256 hash client-side
  and POSTs it to `/__challenge` as an `X-Hashcash-Solution` header before
  the real content is served. This is not one of the standard vendor WAFs
  in the portfolio's playbook (Cloudflare/DataDome/PerimeterX/Akamai/
  Fastly/AWS WAF) -- looks like a homegrown or niche bot-mitigation product,
  and it's applied selectively to feed/sitemap endpoints only, not the
  page-render path. The bare top-level `/sitemap.xml` (a sitemap *index*,
  no article URLs) is NOT gated -- only the per-day sub-sitemaps are.

**Decision:** since this challenge only blocks feed/sitemap discovery
endpoints and the actor's core value (full article text) doesn't need them,
solving the hashcash PoW was not pursued. `latest` mode uses the open
homepage instead (see below). If a future need arises for a true
chronological feed, revisit solving the challenge -- it's computationally
solvable HTTP-only (SHA-256 PoW, no browser JS-VM dependency), just not
attempted in this recon pass.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html` (JSON-LD metadata + HTML body, both required)

`GET https://www.chicagotribune.com/<year>/<month>/<day>/<slug>/`

The page emits a `NewsArticle` JSON-LD block with `headline`, `author`,
`creator` (both present -- `creator` is a plain string-array byline,
`author` a richer object), all three date fields, `articleSection`,
`keywords`, `image`, and `isAccessibleForFree` -- but **no `articleBody`**.

**Paywall flag caveat (same pattern as `latimes-scraper`):**
`isAccessibleForFree` was `false` on every sampled article, but the HTML
body was full-length (6,400+ characters) on all of them regardless -- this
is a metering flag (Tribune Publishing sites use a soft meter, N free
articles/month via client-side JS, not server-side truncation), not an
enforced gate in the scraped data. Passed through raw per convention; do not
assume `false` means the text is a teaser.

Full text comes from HTML: `div.article-body > div.body-copy`, then every
direct-child bare `<p>` tag (no `class` attribute). Ad slots
(`div.dfp-ad`), the Trinity Audio player widget (`div.trinity-tts-pb`,
`div.s2nPlayer`), and inline `<script>` tags are separate sibling elements
at the same level and are excluded automatically since only `<p>` tags are
collected.

### 2. Latest headlines — `S2-homepage` (fallback, not a true feed)

`GET https://www.chicagotribune.com/`

Since `/feed/` is hashcash-gated (see WAF section), `latest` mode scrapes
the **homepage** instead: every `<a href="https://www.chicagotribune.com/
YYYY/MM/DD/...">` that carries a `title` attribute is treated as a
headline link (the anchor itself wraps only a thumbnail `<img>`, no visible
text -- `title` is the only place the headline string lives). Links are
deduplicated by URL, preserving homepage document order.

**Important limitation:** this is "current homepage top stories," **not** a
true reverse-chronological feed. Two effects observed in one sample: (1)
some homepage modules surface stories from several days back alongside
same-day news (dates in the URL ranged from `08/20` to `08/23` in a
same-day pull); (2) evergreen daily columns with static URLs from **past
years** appear in permanent homepage slots (e.g. `/2024/01/01/ask-amy/` --
the URL date is when the column series launched, not today's installment).
Consumers wanting strictly-todays-news should filter the URL date after the
fact, or prefer `article` mode against URLs obtained some other way (e.g. a
Google News search).

## Paywall behavior

Metering flag present (`isAccessibleForFree: false`) but not enforced in
scraped HTML -- see caveat above. Full text available on every sampled
article.

## Known limits

- No true chronological feed available HTTP-only without solving the
  hashcash challenge (not attempted -- see WAF section).
- `latest` mode can return stale evergreen-column URLs mixed with genuine
  same-day news.

## Diff cadence

Quarterly smoke test recommended. In addition to the standard
`test_local.py` check, re-verify `div.article-body > div.body-copy` is
still the body container (Tribune Publishing has redesigned templates
before) and spot-check that `/feed/` is still gated (if it ever opens up,
switch `latest` mode back to RSS for a true chronological feed).
