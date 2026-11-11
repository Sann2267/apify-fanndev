"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): jpost.com (The Jerusalem Post, English-language
Israeli news outlet) has NO active WAF challenge. robots.txt explicitly
allows `Claude-User` (and GPTBot/ChatGPT-User/OAI-SearchBot/Perplexity-User)
with `Allow: /`, only disallowing utility paths (`/showimage.ashx`,
`/premiumlogin/`, `/servlet/`, `/printarticle.aspx`, `/pdf/`, `/directory/`,
`/search;query`, `/comments/`, `/test-ads/`, `/insights/`). chrome124 gets a
clean 200 on homepage (~750KB), article pages, and both sitemap endpoints.
Real 404s confirmed (synthetic out-of-range article ID returns a genuine
Next.js 404 page, HTTP 404). See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.jpost.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap: capped to recent articles, carries title/keywords/
# publication_date inline (no per-article fetch needed for `latest` mode).
# robots.txt also lists a full sitemapindex.xml (jpgooglesitemap/) covering
# the entire archive, but that's for discovery/backfill, not "latest".
LATEST_SITEMAP_URL = f"{BASE_URL}/GoogleNewsSiteMap/GNSiteMap"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
