"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-27): nationalheraldindia.com is fronted by Cloudflare
(server: cloudflare) but presented NO challenge to plain curl_cffi chrome124
impersonation -- homepage, robots.txt, 3 article pages spanning different
sections (Politics, National, International), the news sitemap, and the
site-wide RSS feed all returned clean 200s with full content, no "Just a
moment"/challenge-platform/captcha body markers, no unexpected 403/429/503.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.nationalheraldindia.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed (same URL also served at /feed -- identical content,
# /stories.rss used for consistency with the other Quintype/AssetType CMS
# actors in this portfolio, e.g. newindianexpress-scraper,
# freepressjournal-scraper). Confirmed live on 2026-08-27 -- rich fields
# (title, link, guid, pubDate, atom:author, media:keywords, category,
# content:encoded full-HTML body) spanning many sections, not limited to
# one category.
RSS_URL = "https://www.nationalheraldindia.com/stories.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
