"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): bangkokpost.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, and the
top-stories RSS feed, no cf-ray/x-datadome/_abck/Fastly markers, no challenge
body. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.bangkokpost.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide top-stories feed. Confirmed live and chronological across
# thailand/general and business/general sections in the 2026-08-24 spot
# check, 5 sampled articles all recent.
RSS_URL = "https://www.bangkokpost.com/rss/data/topstories.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
