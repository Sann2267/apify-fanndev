"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): globaltimes.cn (Chinese state media, English
edition) has NO active WAF challenge. robots.txt is a single 2-line file
(`User-agent: *` with no Disallow at all) -- no Claude/GPTBot/anthropic-ai
disallow. chrome124 gets a clean 200 on homepage, article pages, and the
Google News sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.globaltimes.cn"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
