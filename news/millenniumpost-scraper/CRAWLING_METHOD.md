# Crawling Method — Millennium Post

**Last verified:** 2026-08-26

Millennium Post (`millenniumpost.in`) is a Delhi-based English-language
daily newspaper, also publishing print editions in Kolkata.

## Robots.txt

```
User-agent: *
Allow: /

# Block admin and system directories
Disallow: /admin/
Disallow: /xhr/
Disallow: /staging/
... (search/preview/embed/pagination/sorting/filtering param traps, low-value
    internal paths, font files, external social-platform prefixes)

# Allow CSS, JS, and images needed for rendering and Discover
Allow: /*.css$
Allow: /*.js$
Allow: /images/

# Explicitly allow Googlebot-News full access
User-agent: Googlebot-News
Allow: /

Sitemap: http://www.millenniumpost.in/news-sitemap-daily.xml
Sitemap: http://www.millenniumpost.in/sitemap-daily.xml
Sitemap: http://www.millenniumpost.in/sitemap-daily-updated.xml
```

Two `User-agent` groups total (`*` and `Googlebot-News`), both allow-all for
the paths this actor needs (article pages, sitemaps). No
`Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` disallow anywhere, and no plain-English prohibition against
AI/LLM training or scraping in the comments (the comments are all mundane
SEO-crawl-budget notes — admin paths, search/pagination param traps, font
files, social-embed prefixes) — independently re-verified live with a fresh
`curl` fetch during this build. Confirmed crawlable.

## WAF

`millenniumpost.in` sits behind **Cloudflare** (`server: cloudflare`,
`cf-ray` present on every response). No challenge was observed on any path
tried: homepage, `robots.txt`, article pages across 3 different sections
(Business, Nation, Bengal), and `/news-sitemap-daily.xml` all returned a
clean HTTP 200 with `curl_cffi` `chrome124` impersonation on the first try —
even a plain unauthenticated `curl` (no TLS impersonation) got a real 200 on
every one of these paths during recon, so this site does not appear to gate
on TLS fingerprint at all. `chrome124` is still pinned for the actor per the
portfolio-wide default of avoiding the most-blocklisted `chrome131` profile.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.millenniumpost.in/<section>/<slug>-<id>`

The page emits **7** separate `<script type="application/ld+json">` blocks:
`Article`, `NewsArticle`, `Organization`, `WebSite`, `BreadcrumbList`,
`SiteNavigationElement`, `WebPage`. The first two (`Article` and
`NewsArticle`) are near-duplicates carrying identical fields — the extractor
explicitly prefers the `NewsArticle`-typed block (falling back to the
generic `Article` block only if no `NewsArticle` block is present, which was
never observed).

The `NewsArticle` node carries `headline`, `alternativeHeadline`,
`description` (dek, sometimes truncated with a trailing `...` by the CMS),
`articleBody` (full plain-text article, 1,265–4,241 characters across 3
samples), `datePublished`/`dateModified` (ISO 8601 with `+05:30` IST
offset), `keywords` (always an empty string on all 3 samples — this CMS
does not populate the field), `articleSection` (e.g. `"Business"`,
`"Nation"`, `"Bengal"`), `image` (full `ImageObject` with `contentUrl`,
`height`, `width`), `author`, `publisher`, `mainEntityOfPage`, `inLanguage`,
`interactivityType`, `url`.

**Quirk — generic byline:** `author.name` is always `"MPost"` (a site-wide
generic desk credit, `@type: "Person"`, linking to
`https://www.millenniumpost.in/team.mp`) on every sample checked, not a
named individual reporter. Passed through verbatim per raw-passthrough
convention.

No HTML entity/double-escaping quirks observed in any text field on any of
the 3 samples (headline, articleBody, articleSection all come through
clean).

No `isAccessibleForFree`/paywall-signal fields were observed on any sampled
article — Millennium Post's news content does not appear to carry a
schema.org paywall marker, and no truncation or "subscribe to continue
reading" markers were found in `articleBody`.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.millenniumpost.in/news-sitemap-daily.xml`

The site-wide `/rss` and `/feed` endpoints (generator: `Hocalwire`) both
return HTTP 200, but the channel is **empty** — zero `<item>` elements, and
`lastBuildDate` was over a year stale (`13 Aug 2025`) as of this build. A
dead feed, not wired up as a fallback.

`/news-sitemap-daily.xml` is used instead: a Google News sitemap with 273
`<url>` entries observed in one fetch. Each entry carries `loc`,
`news:news/news:publication_date` (real per-article ISO 8601 timestamp with
`+05:30` offset), `news:news/news:title`, and an `image:image/image:loc`.
Confirmed already newest-first in file order (top entry matched the
freshest homepage/business-section headline at fetch time) —
`extract_sitemap_items()` still sorts descending by `publication_date`
defensively, in case that ordering isn't guaranteed on every fetch.

BeautifulSoup's `xml` (lxml-xml) parser resolves the `news:`/`image:`
prefixed tag names directly (`find("news:title")` works as-is on this feed,
unlike some other sites in this portfolio where prefixes get stripped) —
confirmed against a live fetch on 2026-08-26.

## Paywall behavior

None observed. No truncation, no `isAccessibleForFree` marker, no
"subscribe to continue reading" string found on any of the 3 sampled
articles (Business, Nation, Bengal).

## Known limits

- 404s for invented/nonexistent article slugs are **real HTTP 404s**
  (confirmed on a deliberately-invented slug) — no soft-404 quirk observed.
- `keywords` is always an empty string in the JSON-LD on every sample — the
  CMS does not populate this field for this outlet.
- `author` is always the generic `"MPost"` desk byline, never a named
  reporter, on every sample checked.
- `/rss` and `/feed` are dead (200 but zero items, stale `lastBuildDate`) —
  `latest` mode uses `/news-sitemap-daily.xml` instead.
- Only 3 articles sampled in depth (Business, Nation, Bengal), plus one
  invented-slug 404 probe. A structurally different template (e.g. a
  live-blog, opinion/editorial, or photo-gallery page) was not sampled.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Millennium Post redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
