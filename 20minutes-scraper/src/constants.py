"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): 20minutes.fr has NO active WAF challenge. It
sits behind Cloudflare (cf-ray header present) but chrome124 gets a clean
200 with full content on homepage, article pages, and the site-wide RSS
feed -- no challenge body, no 403. 20 Minutes is a free ad-supported daily
(no subscription product), and no paywall marker was found on any sampled
article -- articleBody in JSON-LD is consistently full-length.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.20minutes.fr"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "Une" (front page) feed. Confirmed live, 30 items per fetch.
RSS_URL = "https://www.20minutes.fr/feeds/rss-une.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
