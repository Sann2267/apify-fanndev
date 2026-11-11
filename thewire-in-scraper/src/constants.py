"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): thewire.in (The Wire, India -- independent
digital-native investigative/analysis outlet; NOT related to any "The Wire"
outlet in other countries) sits behind Cloudflare on its main domain
(`server: cloudflare` on `/robots.txt`), but the desktop site itself is a
pure client-side-rendered React SPA -- every path (homepage, article pages,
`/feed`, `/sitemap.xml`, `/wp-json/...`) returns the SAME ~11KB shell with an
empty `<div id="root"></div>` and no server-rendered content or JSON-LD at
all, regardless of TLS profile or User-Agent. Curl/curl_cffi never execute
the site's JS, so this shell carries no usable data.

The site's own client JS reveals the fix: on a mobile User-Agent it redirects
every article path to `m.thewire.in/article/<path>` (see the inline script in
the shell HTML). That `m.thewire.in` mobile subdomain is a SEPARATE, fully
server-side-rendered site (`server: nginx`, no Cloudflare, no challenge of
any kind) that carries real `application/ld+json` `NewsArticle` blocks with
the full article text inline. `curl_cffi` `chrome124` gets clean 200s on
`m.thewire.in` homepage, article pages, and the sitemap on the very first
try -- no warmup-then-retry dance needed, no WAF markers observed anywhere on
this subdomain. `chrome124` is pinned anyway per the portfolio-wide default
of avoiding the most-blocklisted `chrome131` profile even when it currently
works.

Because of this, EVERY article fetch in this actor is done against
`m.thewire.in`, not `thewire.in` -- `normalize_article_url()` in
`extractor.py` rewrites any `thewire.in`/`www.thewire.in` input URL to its
`m.thewire.in/article/...` equivalent before the HTTP call. `m.thewire.in`
URLs (as already emitted by the sitemap, or if a user pastes one directly)
pass through unchanged.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://m.thewire.in"
WARMUP_URL = f"{BASE_URL}/"

# `/feed` and `/rss` on m.thewire.in return a hard, literal 403 ("403
# Forbidden", 134 bytes, no challenge markers) on every sample -- a
# deliberate route block (these paths likely gate a native-app-only feed),
# not a WAF/bot-fingerprint block, since the homepage, article pages, and
# this sitemap all return clean 200s on the same TLS profile with no retry.
# `?feed=rss2` was also tried and just 200s with the homepage HTML again (a
# dead end, not real RSS).
#
# The sitemap index (`/sitemap.xml`, also referenced from m.thewire.in's own
# robots.txt `Sitemap:` directive) breaks the catalog into 53 per-category
# sub-sitemaps with no single site-wide feed. Category ID 1 was confirmed
# live (2026-08-26) to carry a broad, multi-section mix of recent articles
# (politics/law/news/rights samples all seen) with `<loc>`/`<lastmod>`/
# `<image:title>` per entry, already newest-first in file order -- used as
# the default `latest` source since no genuine site-wide feed/API exists.
LATEST_SITEMAP_URL = f"{BASE_URL}/sitemap/category/1/sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
