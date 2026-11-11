"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): theatlantic.com has NO WAF in front of it.
chrome124 returned 200 with full content on homepage, article pages, and the
"best of" RSS feed, no cf-ray/x-datadome/_abck/Fastly markers, no challenge
body. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.

Unlike every other actor in this portfolio, article body text is NOT in the
JSON-LD block here (JSON-LD is metadata-only, `articleBody` absent) -- it
lives in an Apollo/urql GraphQL cache embedded in `__NEXT_DATA__`. See
extractor.py and CRAWLING_METHOD.md for the full extraction path.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.theatlantic.com"
WARMUP_URL = f"{BASE_URL}/"

# Confirmed live and chronological (2026-08-24 spot check, 5 sampled
# articles across ideas/culture/politics verticals).
RSS_URL = "https://www.theatlantic.com/feed/best-of/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
