"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): ghanaweb.com (GhanaWeb, Ghana's largest
English-language news portal, founded 1999) has NO active WAF challenge.
The site is Akamai-fronted (x-akamai-transformed header, mPulse RUM beacon)
but that's CDN/analytics only -- no _abck/bm_sz bot-manager cookie was ever
set, no cf-ray, no challenge body. chrome124 gets a clean 200 on homepage,
article pages, and the Google News sitemap. robots.txt has THREE
User-agent groups (Mediapartners-Google, PetalBot, *) each with its own
dedicated Disallow block directly beneath it -- no shared/merged block
across groups, so no Claude/GPTBot/anthropic-ai disallow anywhere. See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.ghanaweb.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised in robots.txt (updated near-real-time --
# observed items published less than a minute before fetch).
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/news.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
