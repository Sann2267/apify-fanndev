"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): euronews.com (pan-European English-language
news outlet) has NO active WAF challenge. robots.txt returns 200 and
explicitly allows generic bots (`Allow: /`) with no Claude/ClaudeBot/
anthropic-ai/claude-web/claude-user/claude-searchbot disallow (it does
disallow GPTBot, CCBot, Google-Extended specifically, which does not
apply to our default UA). chrome124 gets a clean 200 on homepage,
article pages, and the RSS feed. Real 404s confirmed (synthetic
nonexistent article slug). See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.euronews.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
