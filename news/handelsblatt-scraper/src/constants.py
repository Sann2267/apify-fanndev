"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): handelsblatt.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, and the
site-wide "Schlagzeilen" RSS feed, no cf-ray/x-datadome/_abck/Fastly
markers, no challenge body. chrome124 is pinned per the portfolio-wide
default of avoiding the most-blocklisted profile even when it currently
works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.handelsblatt.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide headlines feed. Confirmed live and chronological across
# politik/finanzen sections in the 2026-08-24 spot check, 8 sampled
# articles all recent.
RSS_URL = "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
