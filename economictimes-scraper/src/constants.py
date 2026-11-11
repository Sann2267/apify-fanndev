"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): economictimes.indiatimes.com has NO WAF in front
of it. chrome124 returned 200 with full content on homepage, article pages,
and RSS feeds, no cf-ray/x-datadome/_abck/Fastly markers, no challenge body.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://economictimes.indiatimes.com"
WARMUP_URL = f"{BASE_URL}/"

# Default site-wide feed. Mixes fresh items with occasional older evergreen
# items (confirmed 2026-08-24) -- callers relying on strict recency should
# check `pubDate` client-side. Per-section feed IDs exist
# (`/rssfeeds/<id>.cms`) but rotate/vary in reliability, so this actor
# standardizes on the one documented, always-live default feed.
RSS_URL = "https://economictimes.indiatimes.com/rssfeedsdefault.cms"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
