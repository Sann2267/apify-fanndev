"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): clarin.com (Clarin, Argentina's largest-
circulation newspaper, Spanish edition) has NO active WAF challenge.
robots.txt is clean -- disallows only `/api/`, `/redaccionfiler/*`,
`/viafoura/*`, a few narrow paths, `/cdn-cgi/`, `/_next/` -- no Claude/
GPTBot/anthropic-ai disallow of any kind, and it advertises three
Sitemap: lines including a Google News sitemap. chrome124 gets a clean
200 on homepage, article pages, and the news sitemap. Real 404s
confirmed (synthetic out-of-range article slug). See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.clarin.com"
WARMUP_URL = f"{BASE_URL}/"

NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/sitemap_google_news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
