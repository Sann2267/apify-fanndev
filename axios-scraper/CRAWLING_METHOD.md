# Crawling Method — Axios

**Last verified:** 2026-08-24

## WAF

**Cloudflare fronts axios.com** (`server: cloudflare`, `cf-ray` present on
every response), but it was **not actively challenging** `curl_cffi`
`chrome124` traffic during recon — homepage, article pages, and the
`api.axios.com/feed/` RSS endpoint all returned clean 200s with full content
and no "Just a moment" / `challenge-platform` body. This is a "Cloudflare
present but bot-management not engaged on these paths" situation, not a
confirmed bypass of an active challenge. If this actor starts seeing 403s in
production, treat it as a fresh WAF-triage case (`.ai/anti-bot/cloudflare.md`)
rather than assuming the existing profile still works — Cloudflare
configurations change without notice.

**TLS profile pinned:** `chrome124`, consistent with the rest of the
portfolio's default (avoids the most-blocklisted `chrome131` profile even
though it also worked in testing).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.axios.com/<yyyy>/<mm>/<dd>/<slug>`

The page carries `__NEXT_DATA__` too (Axios runs on Next.js) but the
JSON-LD block is preferred per project convention (more stable across
redesigns) and already carries everything needed: `headline`, `description`,
`datePublished`/`dateModified`, `image`, `articleSection`, and a
`BreadcrumbList` inside `mainEntityOfPage`. **Important shape quirk:** Axios
emits this as a single `<script type="application/ld+json">` tag containing a
JSON **list** (`[NewsMediaOrganization, NewsArticle]`), not a bare dict like
most other outlets in this portfolio — `extract_article` checks both list and
dict shapes to stay robust if that changes.

### 2. Latest headlines — `S2-rss`

`GET https://api.axios.com/feed/`

Single site-wide RSS 2.0 feed (all sections/verticals mixed, ~1600+ items in
one response). Unusually rich for RSS: `content:encoded` carries the full
article HTML body (not just a teaser), multiple `dc:creator` tags for
co-bylined stories, `media:content`/`media:thumbnail` for the lead image, and
`category` (a single coarse tag like `top`, not a full taxonomy). No
per-section feed was found — `https://www.axios.com/<section>/feed` and
`https://www.axios.com/feed` both 404.

## Paywall behavior

No paywall encountered. Axios content tested here (news articles, not the
subscriber-only Axios Pro verticals) is fully open — both the JSON-LD
description and the RSS `content:encoded` carry the complete article body.

## Known limits

- `latest` mode returns the newest items from one large combined feed — no
  section/vertical filter is exposed by the API.
- `category` in latest mode is a single coarse tag (e.g. `top`), not a full
  section taxonomy — use `articleSection` from article mode for that.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the JSON-LD script tag still contains a
`NewsArticle` entry (list or dict). If Cloudflare starts actively challenging
requests, re-run the profile ladder (`chrome124`/`chrome131`/`safari17_0`/
`firefox133`) before escalating to a browser.
