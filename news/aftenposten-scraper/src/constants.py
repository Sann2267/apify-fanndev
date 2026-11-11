"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): aftenposten.no has NO WAF in front of it. curl_cffi
chrome124 gets 200 on homepage, article pages, and /rss.xml with no cf-ray/
x-datadome/_abck/Fastly markers, no challenge body. robots.txt has no
disallow for Claude/anthropic-ai/GPTBot/ClaudeBot/CCBot/bytespider.

Sampled 10 live articles from /rss.xml (2026-08-24): 8/10 had a `NewsArticle`
ld+json block (mix of `isAccessibleForFree: true/false`), 2/10 (culture/
review pieces) had none at all -- see Known limits in CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.aftenposten.no"
WARMUP_URL = f"{BASE_URL}/"
RSS_URL = f"{BASE_URL}/rss.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
