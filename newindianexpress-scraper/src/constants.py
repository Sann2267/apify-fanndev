"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): newindianexpress.com sits behind Cloudflare
(server: cloudflare, cf-ray present on every response) but presents NO
challenge to plain curl_cffi chrome124 impersonation -- homepage, article
pages across 5 different sections, and the site-wide RSS feed all returned
200 with full content, no "Just a moment"/challenge-platform/captcha body
markers. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.newindianexpress.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide RSS feed (redirect target of /feed). Confirmed live on
# 2026-08-26 -- rich fields (title, link, guid, pubDate, atom:author,
# media:keywords, category, content:encoded full-HTML body) and articles
# spanning many sections (states, cities, entertainment, opinions), not
# limited to one category. Preferred over guessing at a single section feed.
RSS_URL = "https://www.newindianexpress.com/stories.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
