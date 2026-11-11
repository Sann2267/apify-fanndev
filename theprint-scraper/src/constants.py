"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): theprint.in sits behind CloudFront with a custom
origin-side bot check (`X-Powered-By: luroConnect`) that is gated on CDN
CACHE STATE, not on TLS/JA3 fingerprint. `curl_cffi` `chrome124` (and every
other profile tried: chrome131, chrome99_android, safari17_0, edge101)
returns full article HTML instantly whenever CloudFront already has the page
cached (`X-Cache: Hit from cloudfront`). Whenever CloudFront has NOT cached
the page yet (`X-Cache: Miss from cloudfront` -- true for the small number
of very freshly-published/low-traffic articles, and for any URL CloudFront
has never seen), the origin returns a tiny (~1.8KB) "Just a moment..." JS
interstitial that sets a static, non-cryptographic cookie
(`__lc_ch=<epoch>:<hex>`) and reloads -- reproducing that cookie/reload by
hand does NOT clear the check (confirmed: setting the exact cookie value and
re-requesting stays on the challenge), so this is not a solvable HTTP-only
challenge, it is purely a function of whether the CDN edge already has the
page. Sampling the Google News sitemap (see below) at various ages showed
roughly 60-90% of entries already cache-HIT depending on how much organic
traffic they've had; the newest 1-3 items (published within the last few
minutes) are the ones most likely to still be a cache MISS. This affects
`article` mode only when scraping a brand-new/never-visited URL --
already-published, previously-indexed article URLs (the normal scraping
target) reliably return full content. `latest` mode is entirely unaffected
because it reads the sitemap XML directly and never opens individual article
pages. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.

robots.txt (`User-agent: *` / `Allow: /`, explicit `Disallow` list for
search/tracking/ad paths only) has no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai disallow of any kind and no
plain-English AI/LLM-training prohibition in its comments (it has no
comments at all) -- independently re-verified live during this build. Only
`GPTBot` and `CCBot` get a blanket `Disallow: /`; `Google-Extended` is
explicitly `Allow: /`.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://theprint.in"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap (referenced from robots.txt). Confirmed live on
# 2026-08-26: 1000 <url> entries, each carrying loc/news:title/
# news:publication_date/news:keywords/image:loc, timestamps matching
# wall-clock time to the minute. The site-wide /feed RSS and the
# wp-json/wp/v2/posts REST API both 200 but return the SAME ~1.8KB
# "Just a moment" challenge body as an uncached article page (a path-level
# block, not just a cache-state artifact -- confirmed on repeated retries),
# so the Google News sitemap is used instead. sitemap_index.xml (the regular
# Yoast sitemap) also works but only lists per-day archive pages, not
# individual articles directly, so googlenews.xml is preferred as the more
# direct source.
NEWS_SITEMAP_URL = f"{BASE_URL}/googlenews.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
