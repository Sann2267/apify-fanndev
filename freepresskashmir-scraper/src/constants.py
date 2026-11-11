"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): freepresskashmir.news sits behind Cloudflare
(server: cloudflare) but presents NO challenge to plain curl_cffi chrome124
impersonation -- homepage, article pages across news + long-form feature
templates, the post-sitemap.xml, and the site-wide RSS feed all returned 200
with full content, no "Just a moment"/challenge-platform/captcha body
markers. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it also works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://freepresskashmir.news"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide WordPress RSS feed. Confirmed live on 2026-08-26 -- standard
# RSS 2.0 with title/link/guid/pubDate/description/dc:creator/category,
# newest-first, spanning multiple sections (not limited to one category).
RSS_URL = f"{BASE_URL}/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
