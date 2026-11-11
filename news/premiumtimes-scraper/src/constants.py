"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): premiumtimesng.com (Premium Times, Nigerian
independent English-language news outlet) sits behind Cloudflare but shows
NO active challenge for normal traffic -- chrome124 gets a clean 200 on the
homepage, article pages, /feed, and /feed?paged=N. robots.txt is a stock
Yoast SEO block (`User-agent: *` / `Disallow:` empty -- i.e. allow-all) with
no Claude/GPTBot/anthropic-ai disallow of any kind, and only one
user-agent group (no multi-group parser trap to worry about here).

One real quirk found during recon: a small fraction of individual article
URLs intermittently serve a **stale edge-cached Cloudflare JS challenge**
(a `slowAES`-based cookie-setter, ~1.6 KB body, `cf-cache-status: HIT`)
instead of the real page -- confirmed NOT a JA3/TLS block (every profile in
the ladder hit the identical cached response for the same URL) and NOT
IP-reputation (immediately fetching a *different*, never-before-cached
article URL returned the real ~440 KB page on the very first try). Appending
a cache-busting query parameter (e.g. `?_ptscb=<n>`) bypasses the stale edge
cache and returns the real page. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.premiumtimesng.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feed"
RSS_PAGE_SIZE = 15

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
