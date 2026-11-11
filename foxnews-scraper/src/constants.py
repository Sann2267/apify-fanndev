"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): foxnews.com has NO active WAF challenge.
robots.txt (301 bytes) has no Claude/GPTBot/anthropic-ai disallow -- unlike
several other major US outlets screened in this batch (CNN, Politico, The
Hill, USA Today, Boston Globe all explicitly block Claude/anthropic-ai).
chrome124 gets a clean 200 on homepage, article pages, and the site-wide
RSS feed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.foxnews.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide Google Publisher feed. Confirmed live, 25 items per fetch.
RSS_URL = "https://moxie.foxnews.com/google-publisher/latest.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
