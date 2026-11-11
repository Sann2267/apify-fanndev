"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): spiegel.de has NO WAF. chrome124 returned 200
with full content on homepage, article pages, and the site-wide RSS feed,
no cf-ray/x-datadome/_abck markers, no challenge body. `via: 1.1 google`
header indicates a Google Cloud CDN front, not an anti-bot vendor.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.spiegel.de"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide headline feed. Confirmed live, 30 items per fetch, mixed
# sections (ausland/sport/panorama/wirtschaft observed).
RSS_URL = "https://www.spiegel.de/schlagzeilen/index.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
