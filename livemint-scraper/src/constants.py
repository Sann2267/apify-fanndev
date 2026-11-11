"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): www.livemint.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, and the
RSS feed, no cf-ray/x-datadome/_abck/Fastly markers, no challenge body.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works. Site is Next.js
(`x-powered-by: Next.js`) but article data lives in JSON-LD, not
`__NEXT_DATA__`, so the SSR container is not used here.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.livemint.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "news" RSS feed. Chronological, clean CDATA fields, includes
# media:content image. Confirmed live and fresh (2026-08-24).
RSS_URL = "https://www.livemint.com/rss/news"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
