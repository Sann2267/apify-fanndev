"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): ndtv.com sits behind Akamai Bot Manager (ak_bmsc
cookie, akamai-grn header on every response, edgesuite.net "Access Denied"
block page on plain `curl`/unimpersonated TLS clients and on Googlebot's own
UA string). `curl_cffi` `chrome124` impersonation clears it cleanly — 200 on
homepage, section pages, and article pages, no challenge body, no captcha.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted `chrome131` profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.ndtv.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide Feedburner RSS feed. Confirmed live 2026-08-26: 100 items, most
# recent pubDate within minutes of the request. NDTV's own /rss hub page
# (https://www.ndtv.com/rss) is an HTML directory of section-feed links, not
# a feed itself -- this Feedburner mirror is the actual feed endpoint and
# covers all sections (not just one), unlike Hindustan Times where only a
# section-specific feed was found.
RSS_URL = "https://feeds.feedburner.com/ndtvnews-latest"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
