"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): thejakartapost.com has NO active WAF challenge.
robots.txt has no Claude/GPTBot/anthropic-ai disallow (only a handful of
utility paths blocked for `*`). chrome124 gets a clean 200 on homepage,
article pages, and the news sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thejakartapost.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, refreshed continuously -- used as the "latest" feed.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap_news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
