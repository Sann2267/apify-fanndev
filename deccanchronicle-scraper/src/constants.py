"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): deccanchronicle.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, the
site-wide RSS feed, and the news sitemap, no cf-ray/x-datadome/_abck/Fastly
markers, no challenge body. Site sits behind CloudFront + nginx
(`x-cache: Miss from cloudfront`, `server: nginx/1.24.0`) -- CDN, not a bot-
management WAF. chrome124 is pinned per the portfolio-wide default of
avoiding the most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.deccanchronicle.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide RSS feed (served at /rss.xml, self-referencing atom:link points at
# /google_feeds.xml -- both resolve to the same content). Confirmed live and
# chronological on 2026-08-26: lastBuildDate matched wall-clock time, newest
# item was ~1 minute old. Unlike Hindustan Times in this portfolio (which
# only exposes per-section feeds), this is a single site-wide feed covering
# all sections, so no section parameter is needed.
RSS_URL = "https://www.deccanchronicle.com/rss.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
