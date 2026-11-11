"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): mg.co.za has NO active WAF challenge.
robots.txt explicitly ALLOWS Google-Extended (its own dedicated block is
`Allow: /`, not a disallow) and has no Claude/GPTBot/anthropic-ai
disallow at all. chrome124 gets a clean 200 on homepage, article pages,
and the RSS feed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://mg.co.za"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide RSS feed, discovered by path probing (not advertised in
# robots.txt -- only sitemap.xml is listed there, which lacks per-article
# titles, see CRAWLING_METHOD.md).
RSS_URL = f"{BASE_URL}/rss/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-ZA,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
