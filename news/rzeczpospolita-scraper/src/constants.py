"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): rp.pl (Rzeczpospolita, major Polish daily
broadsheet) has NO active WAF challenge. robots.txt is clean of any
Claude/GPTBot/anthropic-ai disallow -- only disallows technical/preview
paths and one specific dead article. chrome124 gets a clean 200 on
homepage, article pages, and the Google News sitemap. Real 404s
confirmed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.rp.pl"
WARMUP_URL = f"{BASE_URL}/"

NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
