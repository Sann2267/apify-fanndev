"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): hindustantimes.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, and the
India-news RSS feed, no cf-ray/x-datadome/_abck/Fastly markers, no challenge
body. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.hindustantimes.com"
WARMUP_URL = f"{BASE_URL}/"

# India-news section feed. Confirmed live with real article links across 5
# samples on 2026-08-24. No single site-wide feed was found during recon
# (unlike Economic Times/LA Times) -- this section feed is used as the
# default per the portfolio convention of preferring a documented, always-
# live feed over guessing at undocumented section-ID paths.
RSS_URL = "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
