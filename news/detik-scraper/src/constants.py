"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): news.detik.com has NO active WAF challenge.
robots.txt (`Allow: /` for `User-agent: *`) has no Claude/GPTBot/anthropic-ai
disallow. chrome124 gets a clean 200 on homepage, article pages, and the
news sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://news.detik.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap for the main "berita" (news) channel -- continuously refreshed.
NEWS_SITEMAP_URL = f"{BASE_URL}/berita/sitemap_news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
