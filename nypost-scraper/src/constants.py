"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): nypost.com has NO WAF in front of it. chrome124
returned 200 with full content on homepage, article pages, and the site-wide
RSS feed, no cf-ray/x-datadome/_abck markers, no challenge body. WordPress
REST API (`/wp-json/`) is locked down (401 "Invalid or missing API key"), so
article body is not available via a JSON endpoint -- extraction goes through
HTML instead of JSON-LD (JSON-LD on this site carries only headline/author/
date metadata, no `articleBody`).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://nypost.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed (WordPress default). Confirmed live, 22 items per fetch,
# mixed sections (us-news/sports/opinion/business).
RSS_URL = "https://nypost.com/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
