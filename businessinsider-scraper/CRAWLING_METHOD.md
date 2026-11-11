# Crawling Method — Business Insider

**Last verified:** 2026-08-24

## WAF

None detected. `businessinsider.com` returns 200 on homepage, article pages, and
the `/rss` feed under `curl_cffi` `chrome124` impersonation with no `cf-ray`,
`x-datadome-cid`, `x-kasada-tier`, `x-akamai-*`, or `Server: Varnish` headers,
and no challenge body markers. No warmup was strictly required, but the client
does a homepage GET first for hygiene/consistency with the rest of the
portfolio.

**TLS profile pinned:** `chrome124` (not `chrome131`) per the portfolio-wide
default of avoiding the most-blocklisted profile even when it currently works.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.businessinsider.com/<slug>-<yyyy>-<m>`

The article page carries a rich `NewsArticle` JSON-LD block directly as a
top-level dict (not wrapped in a `@graph` list): `headline`, `author` (array
with `jobTitle` and per-author profile URL), `editor`, `datePublished`/
`dateModified`, `description`, `image`, and a full `NewsMediaOrganization`
`publisher` block (masthead, ethics policy, awards, social links). This is
passed through verbatim (raw-passthrough convention) — no `__NEXT_DATA__`
container was found on this site, so JSON-LD is both the primary and only
strategy.

### 2. Latest headlines — `S2-atom`

`GET https://www.businessinsider.com/rss`

This is an **Atom** feed (`<feed>/<entry>`), not RSS 2.0 — confirmed by the
`xmlns="http://www.w3.org/2005/Atom"` namespace. Its own `<subtitle>` states
"All Content from Business Insider **Excluding Premium**", so this feed
naturally excludes subscriber-only articles — no paywall-detection logic
needed on the `latest` path. Each `<entry>` carries `title`, `id` (the
canonical article URL), `updated`, `content` (full HTML body — unusually rich
for an RSS/Atom feed, most outlets only give a teaser), and `category` terms.
No `dc:creator` observed in entries; author attribution is only available via
the article-page JSON-LD `author` array. The feed also exposes a `rel="next"`
pagination link, not used here since `limit` (max 20) is well under one page
(20 entries/page).

## Paywall behavior

Business Insider runs a metered paywall on some articles ("Insider" premium
tier), but the `/rss` feed explicitly filters those out (see above), and the
JSON-LD block on premium articles was not tested for truncation since it's
out of scope — this actor does not attempt to defeat any paywall.

## Known limits

- `latest` mode returns whatever is on the first page of `/rss` (≈20 items,
  newest first, all sections mixed) — no per-section feed was found.
- Author attribution in `latest` mode is not available (Atom feed carries no
  `dc:creator`); use `article` mode on a specific URL for full byline data.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` JSON-LD block is still present. If
Business Insider adds a `@graph`-wrapped JSON-LD or migrates to a Next.js/
React SSR container, `extract_article` will raise `UnexpectedShape` and the
run will fail loudly rather than emit corrupt records.
