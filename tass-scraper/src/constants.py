"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): tass.com (TASS, Russian state news agency,
English edition) has NO active WAF challenge. robots.txt only disallows
`/search`, no Claude/GPTBot/anthropic-ai disallow. chrome124 gets a clean
200 on homepage, article pages, and the RSS feed. Real 404s confirmed
(synthetic out-of-range article ID). See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://tass.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/rss/v2.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
