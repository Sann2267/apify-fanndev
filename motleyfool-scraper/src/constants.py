"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): fool.com (The Motley Fool) has NO active WAF
challenge. robots.txt is a standard `Disallow` list for functional/paid
paths (`/account/`, `/login/`, `/investing/stocks/`, `/free-report`,
etc.) with no Claude/GPTBot/anthropic-ai disallow -- article paths under
`/investing/<year>/<month>/<day>/<slug>/` are not disallowed. chrome124
gets a clean 200 on homepage, article pages, and the RSS feed. Real 404s
confirmed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.fool.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feeds/index.aspx"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
