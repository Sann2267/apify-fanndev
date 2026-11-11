"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): berlingske.dk has NO WAF in front of it. curl_cffi
chrome124 gets 200 on homepage, article pages, and /news-sitemap.xml with no
cf-ray/x-datadome/_abck/Fastly markers, no challenge body. robots.txt blocks
GPTBot and CCBot but has NO disallow for Claude/ClaudeBot/Claude-Web/
anthropic-ai -- checked by exact bot name, not just a blanket rule.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.berlingske.dk"
WARMUP_URL = f"{BASE_URL}/"
SITEMAP_NEWS_URL = f"{BASE_URL}/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
