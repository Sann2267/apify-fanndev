"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): punchng.com (The Punch, Nigeria's most-read
newspaper) sits behind Cloudflare (`server: cloudflare`, `cf-ray` present)
but shows NO active JA3/TLS-fingerprint challenge for normal traffic --
`curl_cffi` `chrome124` gets a clean 200 on the homepage, article pages, and
`/feed`. No stale-edge-cache quirk observed (unlike premiumtimesng.com) on
the samples checked. robots.txt is a stock Yoast SEO block (`User-agent: *`
/ `Disallow:` empty -- allow-all) with no Claude/ClaudeBot/anthropic-ai
disallow of any kind, and only one user-agent group.

Nonexistent article slugs return a REAL HTTP 404 (not a soft-404 like
premiumtimesng.com) -- confirmed on a deliberately-invented slug.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://punchng.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feed"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
