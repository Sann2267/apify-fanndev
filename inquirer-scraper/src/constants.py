"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): inquirer.net has NO active WAF challenge.
robots.txt has no Claude/GPTBot/anthropic-ai disallow. chrome124 gets a
clean 200 on homepage, article pages (across subdomains --
newsinfo.inquirer.net, lifestyle.inquirer.net, etc.), and the site-wide
RSS feed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.inquirer.net"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide feed covering all verticals/subdomains. Confirmed live, ~20 items/fetch.
RSS_URL = f"{BASE_URL}/fullfeed"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-PH,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
