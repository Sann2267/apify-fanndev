"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-27): businesstoday.in has NO WAF gating plain HTTP.
`curl_cffi` `chrome124` (no warmup-then-retry dance needed) returned 200 with
full content on the homepage, article pages across multiple verticals
(india, latest/economy), the news sitemap, and the site-wide "latest" RSS
feed. The homepage `server` response header is `itgdweb` -- confirming
Business Today shares the same "India Today Group Digital" (ITGD) CMS/CDN
infrastructure as `indiatoday-scraper` (same Living Media / India Today
Group publisher). `chrome124` is pinned here for consistency with the rest
of the portfolio and as cheap insurance against Bot Manager being turned on
more strictly later.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.businesstoday.in"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "latest" feed, confirmed live 2026-08-27: 114 items mixing
# multiple verticals/sections (economy, markets, india, world, tech...),
# each carrying title/link/description/pubDate/guid. A genuine site-wide
# feed, same tier as indiatoday-scraper's /rss/home.
RSS_URL = "https://www.businesstoday.in/rss/latest.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
