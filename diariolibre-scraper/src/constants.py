"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): diariolibre.com (Diario Libre, Dominican
Republic national newspaper) has NO active WAF challenge. robots.txt only
disallows `/xstatic/` and `/XStatic/` -- a single `User-agent: *` group,
no separate Claude/ClaudeBot/anthropic-ai group at all (unlike several
other outlets screened in the same batch that explicitly block it).
chrome124 gets a clean 200 on homepage (IIS server, no cf-ray/WAF cookie),
article pages, `/sitemap.xml`, `/sitemapnews`, and `/feed/portada.xml`.
Real 404s confirmed (synthetic out-of-range article id). See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.diariolibre.com"
WARMUP_URL = f"{BASE_URL}/"

# WordPress-adjacent custom CMS RSS feed for the front page -- confirmed to
# carry the FULL article body as HTML inside a CDATA-wrapped <description>,
# not just a teaser. Chosen over /sitemapnews (Google News sitemap, also
# confirmed working) because it's a single request with richer fields
# (readingtime, media:content image, full taxonomy) -- see CRAWLING_METHOD.md.
RSS_URL = f"{BASE_URL}/feed/portada.xml"

# Google News sitemap, advertised in robots.txt -- confirmed working
# fallback source for `latest` mode, not used by default.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemapnews"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-DO,es;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
