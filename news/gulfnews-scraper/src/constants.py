"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): gulfnews.com has NO active WAF challenge.
robots.txt has no Claude/GPTBot/anthropic-ai disallow (unlike Khaleej
Times, Haaretz, and Jerusalem Post, all screened in the same batch and
found to explicitly block Claude). chrome124 gets a clean 200 on
homepage, article pages, and the news sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://gulfnews.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, continuously refreshed. Advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/news_sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AE,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
