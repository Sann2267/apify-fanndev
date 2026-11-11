"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): bild.de has NO WAF in front of it. curl_cffi
chrome124 gets 200 on homepage, article pages, and /sitemap-news.xml with no
cf-ray/x-datadome/_abck/Fastly markers, no challenge body. robots.txt has no
disallow for Claude/anthropic-ai/GPTBot/ClaudeBot/CCbot/bytespider.

BILD enforces "BILDplus" — a genuine (not cosmetic) paywall on a subset of
articles: JSON-LD `isAccessibleForFree: false` correlates with a teaser body
of ~400-650 chars vs ~1800-4700 chars for free articles (sampled 12 live
articles, 2026-08-24). Same tier as business-standard-scraper.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.bild.de"
WARMUP_URL = f"{BASE_URL}/"
SITEMAP_NEWS_URL = f"{BASE_URL}/sitemap-news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
