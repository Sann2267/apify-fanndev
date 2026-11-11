"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): thenationalnews.com (Arc Publishing / Washington
Post-owned platform, same CMS family as washingtonpost-scraper) has NO
active WAF challenge. robots.txt has no Claude/GPTBot/anthropic-ai
disallow (only a generic Googlebot-Image image-crawl restriction).
chrome124 gets a clean 200 on homepage, article pages, and the Arc
outbound news sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thenationalnews.com"
WARMUP_URL = f"{BASE_URL}/"

# Arc Publishing outbound news sitemap, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/arc/outboundfeeds/news-sitemap/?outputType=xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AE,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
