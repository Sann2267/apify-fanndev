"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): independent.co.uk has NO active WAF challenge.
robots.txt is a generic Drupal-style boilerplate with no Claude/GPTBot/
anthropic-ai disallow of any kind (only blocks `Nutch` outright and some
internal paths). chrome124 gets a clean 200 on homepage, article pages,
and the Google News sitemap. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.independent.co.uk"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/googlenews"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
