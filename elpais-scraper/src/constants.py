"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-25): english.elpais.com (EL PAIS, Spain's largest
newspaper, English edition) has NO active WAF challenge. robots.txt has
a single `User-agent: * / Allow: /` group plus a long list of individually
named blocked-bots -- no Claude/GPTBot/anthropic-ai/CCBot entry anywhere.
chrome124 gets a clean 200 on homepage, article pages, and the RSS feed.
Real 404s confirmed (synthetic out-of-range article slug). See
CRAWLING_METHOD.md.
"""

# chrome124 lost the homepage in 2026-10 (403); "chrome" (newest) still gets 200.
TLS_PROFILE = "chrome"

BASE_URL = "https://english.elpais.com"
WARMUP_URL = f"{BASE_URL}/"

# Discovered via <link rel="alternate" type="application/rss+xml"> on the
# homepage. Lives on a separate feeds.elpais.com subdomain (Varnish-fronted,
# but the feed endpoint itself returns a clean 200 -- only /robots.txt on
# that subdomain 403s, which is irrelevant to fetching the feed itself).
RSS_URL = "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
