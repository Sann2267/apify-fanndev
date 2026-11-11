"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): telanganatoday.com has NO WAF in front of it.
chrome124 returned 200 with full content on the homepage, article pages,
the site-wide RSS feed, the news sitemap, and a deliberately-wrong 404 URL
(correctly reported as HTTP 404, redirected to /404.html), no
cf-ray/x-datadome/_abck/Fastly markers, no challenge body. Site sits behind
CloudFront + nginx (`x-cache: Miss/Hit from cloudfront`,
`server: nginx/1.24.0 (Ubuntu)`) -- CDN, not a bot-management WAF. chrome124
is pinned per the portfolio-wide default of avoiding the most-blocklisted
profile even when it currently works. `www.telanganatoday.com` redirects to
the bare `telanganatoday.com` host.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://telanganatoday.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide WordPress RSS feed. Confirmed live and chronological on
# 2026-08-26: lastBuildDate matched wall-clock time, newest item was minutes
# old. 500 items returned per fetch (larger than most portfolio feeds, but
# extractor slices to the requested `limit`). Carries full HTML article text
# in `content:encoded`, so `latest` mode needs no per-article follow-up
# request.
RSS_URL = "https://telanganatoday.com/feed"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
