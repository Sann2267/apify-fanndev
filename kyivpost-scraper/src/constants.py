"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): kyivpost.com (Kyiv Post, English-language
Ukrainian news outlet) has NO active WAF challenge. robots.txt only
disallows `/login`, `/stats-by-authors/`, and various tracking-parameter
query strings -- no Claude/GPTBot/anthropic-ai disallow. chrome124 gets a
clean 200 on homepage, article pages, the news sitemap, and the RSS feed.
Real 404s confirmed (synthetic out-of-range `/post/<id>`). See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.kyivpost.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feed"
NEWS_SITEMAP_INDEX_URL = f"{BASE_URL}/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
