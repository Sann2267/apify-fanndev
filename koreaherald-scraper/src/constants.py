"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): koreaherald.com has NO active WAF challenge.
robots.txt is a minimal 5-line file (`Allow: /`, disallows a few internal
CMS paths) with no Claude/GPTBot/anthropic-ai disallow at all. chrome124
gets a clean 200 on homepage, article pages, and the latest-articles
sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.koreaherald.com"
WARMUP_URL = f"{BASE_URL}/"

# Rolling "latest articles" news sitemap, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap/latest-articles"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
