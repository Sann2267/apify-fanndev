"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): UzDaily is an Uzbekistan business/news portal.
The bare domain `uzdaily.uz` 301-redirects to `www.uzdaily.uz`; the site is
multi-language (`/ru/`, `/en/`, `/uz/`, `/uzc/`) and this actor is scoped to
the English edition (`/en/` path prefix), matching the outlet's stated
"English-language business/news portal" identity.

No active WAF challenge was found: plain `curl` and `curl_cffi
impersonate="chrome124"` both get clean 200s of identical shape, served
directly by nginx (`Server: nginx/1.28.1`) -- no Cloudflare/challenge
markers observed. Retry/backoff scaffolding kept anyway per portfolio
convention. See CRAWLING_METHOD.md for full recon notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.uzdaily.uz"
WARMUP_URL = f"{BASE_URL}/en/"

# Standard RSS 2.0 feed, English edition -- newest-first, ~20 items fixed.
LATEST_FEED_URL = f"{BASE_URL}/en/rss/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
