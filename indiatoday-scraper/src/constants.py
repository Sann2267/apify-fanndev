"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): indiatoday.in has NO WAF gating plain HTTP.
A bare `curl` (no TLS impersonation at all) returned 200 with full content on
the homepage, article pages across every vertical (business/india/technology/
movies/sports/world/science/education/horoscopes/cities), video pages, the
news sitemap, and the site-wide RSS feed. Akamai response headers are present
(`itgd-akmttl`, `Akamai-GRN`) -- confirming Akamai fronts the CDN -- but no
Bot Manager challenge, `Access Denied` page, or JS-challenge body was
observed at any point (unlike `ndtv-scraper`, also Akamai-fronted, which does
gate on TLS fingerprint). `chrome124` is still pinned here for consistency
with the rest of the portfolio and as cheap insurance against Akamai turning
on stricter bot management later.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.indiatoday.in"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "Latest Stories" feed, confirmed live 2026-08-26: 130+ items
# mixing every vertical (India, World, Business, Technology, Movies, Sports,
# Cities, Horoscopes...), freshest pubDate within minutes of the request.
# This is a genuine site-wide feed (unlike hindustantimes-scraper, which only
# has a section-specific feed) -- same tier as ndtv-scraper's Feedburner feed.
RSS_URL = "https://www.indiatoday.in/rss/home"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
