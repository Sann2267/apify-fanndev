"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): channelnewsasia.com (Mediacorp, Singapore) has NO
active WAF challenge. `robots.txt` has no Claude/GPTBot/anthropic-ai disallow
(Drupal-generated file, only disallows admin/search/user paths for `*`).
chrome124 gets a clean 200 on homepage, article pages, and the site-wide RSS
feed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.channelnewsasia.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed, explicitly allowed in robots.txt. Confirmed live, 20 items/fetch.
RSS_URL = f"{BASE_URL}/api/v1/rss-outbound-feed"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-SG,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
