"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): dailypost.ng (Daily Post Nigeria) sits behind
Cloudflare (`server: cloudflare`, `cf-apo-via: tcache` -- Cloudflare's
"Automatic Platform Optimization for WordPress" caching layer) but shows NO
active JA3/TLS-fingerprint challenge -- a plain `requests` baseline (no TLS
impersonation at all) gets a clean 200 on the homepage. `curl_cffi`
`chrome124` is used anyway for portfolio-wide consistency and resilience
against a future fingerprint-gate rollout, not because it was required to
get past a block.

robots.txt (independently re-fetched during this build):

    User-agent: *
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php

    User-agent: bingbot
    Disallow: /search/

    Sitemap: https://dailypost.ng/sitemap_index.xml

    #WP Import Export Rule
    User-agent: *
    Disallow: /wp-content/uploads/wp-import-export-lite/

No Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
disallow anywhere, no blanket `Disallow: /`, and no plain-English comment
prohibiting AI/LLM use -- the only comment is a WP plugin label. Confirmed
crawlable for both article pages and `/feed/`.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed. A 200-OK
non-article page (e.g. `/privacy-policy/`) carries ZERO
`application/ld+json` script blocks at all (not even a non-NewsArticle one)
-- simpler to detect than Guardian Nigeria/Punch, which still emit a
graph without a NewsArticle node on non-article pages.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://dailypost.ng"
WARMUP_URL = f"{BASE_URL}/"

# WordPress core feed. Confirmed clean 200, real per-article dc:creator and
# categories (unlike punchng.com's /feed, which has a constant generic
# creator and empty categories on every item) -- no sitemap detour needed.
RSS_URL = f"{BASE_URL}/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
