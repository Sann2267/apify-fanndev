"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): freepressjournal.in sits behind Cloudflare
(server: cloudflare, cf-ray present on every response) but presents NO
challenge to plain curl_cffi chrome124 impersonation -- homepage, 3 article
pages across different sections (Bhopal, Education, Lifestyle), the
news-sitemap, and the site-wide stories.rss feed all returned 200 with full
content, no "Just a moment"/challenge-platform/captcha body markers.
chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.freepressjournal.in"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide RSS feed (same Quintype/AssetType CMS pattern as other India
# actors in this portfolio, e.g. newindianexpress-scraper). Confirmed live
# on 2026-08-26 -- rich fields (title, link, guid, pubDate, atom:author,
# media:keywords, category, content:encoded full-HTML body) spanning many
# sections. NOT blocked by robots.txt (the `Disallow: */feed` rule only
# matches paths literally ending in "/feed"; "/stories.rss" is a distinct
# top-level path and is unaffected).
RSS_URL = "https://www.freepressjournal.in/stories.rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# freepressjournal.in's soft-404: a nonexistent slug returns HTTP 200 with
# an EMPTY body and a non-standard `Refresh: 0;url=.../404` response header
# instead of a real HTTP redirect or 404 status. curl_cffi does not follow
# `Refresh` headers (only real Location-based redirects), so this shows up
# as a 200 with near-zero content length. Real article pages are always
# 100KB+, so a low byte-count threshold reliably distinguishes the two.
SOFT_404_MAX_BYTES = 1000
