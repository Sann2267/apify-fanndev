# Crawling Method — The Wire (India)

**Last verified:** 2026-08-26

`thewire.in` — The Wire, India's independent digital-native investigative/
analysis outlet. **Not related to any "The Wire" outlet in other countries.**

## robots.txt

`https://thewire.in/robots.txt` returns 200 (served through Cloudflare):

```
User-agent: *
Allow: /
Disallow: /*?fromNewsdog*
```

Allow-all with a single query-param exclusion (a referral-tracking param,
unrelated to this actor). No Claude/ClaudeBot/Claude-Web/Claude-SearchBot/
anthropic-ai disallow of any kind, no blanket `Disallow: /`, and no
natural-language prohibition against AI/LLM training or scraping anywhere in
the file. `m.thewire.in/robots.txt` (the subdomain this actor actually
fetches from — see below) is equally permissive:

```
User-agent: *
Allow: /
Sitemap: https://m.thewire.in/sitemap.xml
```

## WAF / architecture — the key finding

`thewire.in` (desktop) sits behind Cloudflare (`server: cloudflare` header)
but returns a **plain 200, not a WAF challenge**, on every path tried —
homepage, article pages, `/feed`, `/sitemap.xml`, `/wp-json/wp/v2/posts`, even
a deliberately-invented article slug. The catch: **every single one of those
paths returns the exact same ~11KB HTML shell** — an empty
`<div id="root"></div>` with no server-rendered content, no JSON-LD, nothing.
This is a pure client-side-rendered React SPA (bundle at `/app.<hash>.js`);
the server does no routing at all, it always serves the same shell and lets
client-side JS render everything after the fact. `curl`/`curl_cffi` never
execute that JS, so this shell is a dead end for scraping — this is NOT a
bot-block, plain `curl` with a bare User-Agent gets the identical 200 shell
that `curl_cffi chrome124` gets.

**The fix is in the shell's own JS**: an inline script redirects any
mobile-User-Agent visitor from `https://thewire.in/<path>` to
`https://m.thewire.in/article/<path>`. That `m.thewire.in` mobile subdomain is
a completely separate, genuinely server-side-rendered site — different
backend (`server: nginx`, no Cloudflare at all) — that serves full HTML with
real `application/ld+json` `NewsArticle` blocks inline. `curl_cffi chrome124`
gets a clean 200 on `m.thewire.in` homepage, article pages, and the sitemap on
the first try, with none of the`BLOCK_MARKERS` this portfolio checks for
(`Just a moment`, `challenge-platform`, `cf-mitigated`, `captcha-delivery.com`,
etc.) ever observed. **Every article fetch in this actor therefore targets
`m.thewire.in`, not `thewire.in`.**

`normalize_article_url()` in `src/extractor.py` rewrites any
`thewire.in`/`www.thewire.in` article URL a user supplies to its
`m.thewire.in/article/...` equivalent before the HTTP call. `m.thewire.in`
URLs (as already emitted by the sitemap, or pasted directly) pass through
unchanged. This mirrors the desktop shell's own JS rewrite rule
(`url.replace('https://thewire.in/', 'https://m.thewire.in/article/')`) —
confirmed correct by cross-checking the `mainEntityOfPage` field on 4 sampled
`m.thewire.in` articles, which always resolves back to the matching
`https://thewire.in/<section>/<slug>` canonical URL.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://m.thewire.in/article/<section>/<slug>`

Each article page emits 7 separate `application/ld+json` blocks
(`NewsArticle`, `WebPage`, `ProfilePage`, `BreadcrumbList`,
`NewsMediaOrganization`, `WebSite`, `SiteNavigationElement`) —
`extract_article` picks out the `NewsArticle` one specifically. That node
carries `articleBody` with the **full plain-text article** (3,680–14,751
characters across 4 samples), `headline`, `description`, `keywords`
(comma-separated string), `author` (a single `Person` object — `{"@type":
"Person", "name": ..., "url": "https://m.thewire.in/author/..."}` — not a
list, unlike Hindustan Times' `Organization`-array shape), `publisher`
(`Organization` with a `logo` `ImageObject`), `image`/`thumbnailUrl`,
`speakable`, and `datePublished`/`dateModified` (ISO 8601 with `+05:30` IST
offset).

**Quirk:** `mainEntityOfPage` carries the **canonical desktop** URL
(`https://thewire.in/<section>/<slug>`), while `url` carries the
**m.thewire.in** URL actually fetched — these are deliberately different
fields and both are passed through raw. Downstream consumers wanting the
"real" public-facing URL should prefer `mainEntityOfPage`.

**No paywall markers observed:** `isAccessibleForFree`/`hasPart` are absent
from every sampled article's JSON-LD (checked 4 samples across
politics/law/news/rights sections) — consistent with The Wire's public
donor-funded, no-paywall model.

**No double-encoding / mojibake quirk:** curly quotes and other non-ASCII
punctuation in `headline`/`articleBody` are correctly UTF-8-encoded
(`content-type: text/html; charset=utf-8`, confirmed via raw byte inspection
— e.g. `’` is the proper 3-byte `\xe2\x80\x99` sequence, not a
double-encoded artifact). Terminal/editor tools that assume a different
encoding may render these as `�`, but the underlying bytes are correct.

No `__NEXT_DATA__` was found on `m.thewire.in` — this subdomain does not
expose page state via Next.js SSR data injection either; it's a distinct,
simpler server-rendered template ("sortd" branding appears in some asset
paths, likely a headless-CMS delivery layer, not Next.js/WordPress REST in
the conventional sense — `/wp-json/wp/v2/posts` 404s on `m.thewire.in`).

### 2. Latest headlines — `S2-sitemap`

`GET https://m.thewire.in/sitemap/category/1/sitemap.xml`

`/feed`, `/feed/`, and `/rss` on `m.thewire.in` all return a **hard, literal
403** (`403 Forbidden`, 134 bytes, no challenge markers) — a deliberate route
block (these paths likely gate a native-app-only feed), not a WAF/bot
fingerprint block, since the homepage/article pages/sitemap on the same
profile all 200 cleanly with no retry needed. `?feed=rss2` was also tried and
just 200s with the homepage SPA shell again (a dead end, not real RSS).
Plain `curl` (no impersonation at all) got the exact same 403 on `/feed`,
confirming it's not a TLS-fingerprint gate either.

`m.thewire.in/sitemap.xml` (referenced from `m.thewire.in/robots.txt`'s
`Sitemap:` directive) is a `sitemapindex` fanning out to 53 per-category
sub-sitemaps (`/sitemap/category/<id>/sitemap.xml`) — no single site-wide
feed exists. Category ID **1** was confirmed live (2026-08-26) to carry a
broad, multi-section mix of recent articles (politics/law/news/rights samples
all observed in the top entries) — used as the default `latest` source since
no genuine site-wide feed/API exists on this subdomain. Each `<url>` entry
carries `<loc>`, `<lastmod>` (ISO 8601, `+05:30` offset), and an
`<image:image>` block with `<image:title>`/`<image:loc>` — **no dedicated
per-item `<title>` tag outside the image block**, and no Google News sitemap
namespace (`news:*`) like some other outlets in this portfolio
(guardian-nigeria, scroll.in) — `extract_sitemap_items` uses `image:title` as
the headline. Entries were already newest-first in file order on the sample
taken, but are sorted descending by `pubDate` defensively anyway.

## Paywall behavior

No paywall markers or truncation observed on any sampled article.

## 404 behavior

A deliberately-invented article slug on `m.thewire.in` returns a real HTTP
404 with a "Page not found" body (no ld+json) — no soft-404 quirk observed.
The desktop `thewire.in` domain, by contrast, returns 200 for literally any
path (including invented ones) since it's a client-side-rendered SPA shell
with no server-side routing at all — this is exactly why article fetches are
routed through `m.thewire.in` instead, where real HTTP status codes are
meaningful.

## Known limits

- `latest` mode only covers category ID 1's sitemap by default — the other
  52 per-category sitemaps exist but aren't exposed as an input option; add
  one if section-specific latest-mode coverage becomes a requirement.
- `image` means different things in the two modes: a full `ImageObject` dict
  in article mode, a bare URL string in latest mode (from the sitemap's
  `image:loc`) — both are raw passthrough, not normalized to match.
- `author` was a single `Person` dict on every sample seen; a multi-byline
  article (if one exists) may emit a list instead — not observed, handled by
  raw passthrough either way.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block on `m.thewire.in`
still carries `articleBody`. If The Wire redesigns either the desktop SPA's
mobile-redirect rule or the `m.thewire.in` page template, `extract_article`
will raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
