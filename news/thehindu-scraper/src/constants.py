"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): thehindu.com has NO active WAF challenge. It
sits behind Cloudflare (cf-ray header present) but chrome124 gets a clean
200 on homepage, article pages, and the site-wide RSS feed -- no challenge
body. Unusually for this portfolio, the site emits NO `application/ld+json`
at all -- structured data is schema.org **microdata** (itemprop/itemscope
attributes) instead. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thehindu.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed. Confirmed live, 60 items per fetch.
RSS_URL = "https://www.thehindu.com/feeder/default.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
