"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): www.business-standard.com has NO WAF in front of
it. chrome124 returned 200 with full content on homepage, article pages, and
RSS feeds, `server: nginx`, no cf-ray/x-datadome/_abck/Fastly markers, no
challenge body. chrome124 is pinned per the portfolio-wide default of
avoiding the most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.business-standard.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "Latest News" feed, confirmed chronological (lastBuildDate
# matches request time at recon). Discovered via the feed directory page at
# /rss/home-page.rss -- dozens of section/numeric-ID feeds exist
# (markets-106.rss, cricket-218.rss, etc.) but this is the one documented,
# always-live combined feed. NOTE: a numeric-ID guess (latest-news-176.rss)
# turned out to be a stale unrelated "Bs Motoring" feed from 2023 -- don't
# guess numeric feed IDs, use the named /rss/latest.rss path instead.
RSS_URL = "https://www.business-standard.com/rss/latest.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
