"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): latimes.com has NO WAF in front of it. chrome124
returned 200 with full content on homepage, article pages, and the site-wide
RSS feed, no cf-ray/x-datadome/_abck/Fastly markers, no challenge body.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.latimes.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed. Confirmed live and chronological across politics/business/
# california/sports sections (2026-08-24 spot check, 5 sampled articles all
# from the last 3 days).
RSS_URL = "https://www.latimes.com/rss2.0.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
