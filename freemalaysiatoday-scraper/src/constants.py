"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): freemalaysiatoday.com sits behind Cloudflare
(cf-ray header present on homepage response) but shows NO active challenge
-- curl_cffi chrome124 gets a clean 200 on the homepage, article pages, and
the RSS feed, with no challenge body. robots.txt explicitly ALLOWS
Claude-Web, ClaudeBot, and anthropic-ai (each gets its own stanza with
`Allow: /`), only disallowing `/wp-admin/`, `/wp-includes/`, `/api/`, and
`/video-admin/`. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.freemalaysiatoday.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide headlines feed. Confirmed live, 50 items per fetch -- and
# unusually rich: each <item> carries the FULL article HTML in
# <content:encoded>, not just a teaser.
RSS_URL = f"{BASE_URL}/feeds/rss/headlines"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-MY,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
