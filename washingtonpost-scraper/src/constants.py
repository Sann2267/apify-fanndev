"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-09): washingtonpost.com has NO WAF in front of it.
Every curl_cffi impersonation profile (chrome131/124/116/99_android/safari17_0/
edge101) returned 200 with full content on both the homepage and article pages,
no cf-ray/x-datadome/_abck/Fastly markers, no challenge body. chrome124 is
pinned anyway (not chrome131) per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works — cheap insurance against
a future WAF rollout.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.washingtonpost.com"
WARMUP_URL = f"{BASE_URL}/"
RSS_BASE = "https://feeds.washingtonpost.com/rss"

# Confirmed-live RSS sections (2026-08-09). Others (technology, sports,
# health-science, climate-environment, education, well-being) 400/404 at
# this path — Washington Post moved or renamed those feeds.
RSS_SECTIONS = [
    "politics",
    "national",
    "world",
    "business",
    "entertainment",
    "opinions",
    "lifestyle",
    "local",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
