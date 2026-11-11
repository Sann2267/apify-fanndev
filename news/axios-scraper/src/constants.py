"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): axios.com sits behind Cloudflare (cf-ray present
on every response) but it is NOT actively challenging curl_cffi traffic —
chrome124 returned 200 with full content on homepage, article pages, and the
RSS feed, no "Just a moment" / challenge-platform body. Treat as "Cloudflare
fronting, bot-management off for these paths" rather than "no WAF" -- if this
ever starts 403'ing, escalate per .ai/anti-bot/cloudflare.md before assuming
IP block.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.axios.com"
WARMUP_URL = f"{BASE_URL}/"

# Single site-wide feed, all sections mixed, served from the api subdomain.
RSS_URL = "https://api.axios.com/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
