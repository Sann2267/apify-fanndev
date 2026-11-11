"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): eluniversal.com.mx (Arc Publishing, same CMS
family as gulfnews-scraper/thenational-scraper) has NO active WAF
challenge. robots.txt only blocks generic offline-downloader tools
(HTTrack, WebZIP, wget, etc.) and Bytespider -- no Claude/GPTBot/
anthropic-ai disallow, and Google-Extended is explicitly grouped with the
*allowed* Googlebot user-agents rather than disallowed. chrome124 gets a
clean 200 on homepage, article pages, and the Arc outbound news sitemap.
See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.eluniversal.com.mx"
WARMUP_URL = f"{BASE_URL}/"

# Arc Publishing outbound rolling news sitemap, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/arc/outboundfeeds/news/?outputType=xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
