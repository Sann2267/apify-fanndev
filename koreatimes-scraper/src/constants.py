"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): koreatimes.co.kr has NO active WAF challenge.
robots.txt blocks a handful of generic scraping/AI-training bots
(Bytespider, Amazonbot, DataForSeoBot) but has no Claude/GPTBot/
anthropic-ai disallow. chrome124 gets a clean 200 on homepage, article
pages, and the news sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.koreatimes.co.kr"
WARMUP_URL = f"{BASE_URL}/www/"

# Rolling news sitemap (reached via sitemap.xml -> sitemap-sections.xml ->
# this file), advertised transitively from robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap/news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
