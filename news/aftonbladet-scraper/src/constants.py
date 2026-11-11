"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): aftonbladet.se has NO WAF in front of it. curl_cffi
chrome124 gets 200 on homepage, article pages, and /rss.xml with no cf-ray/
x-datadome/_abck/Fastly markers, no challenge body. robots.txt has no
disallow for Claude/anthropic-ai/GPTBot/ClaudeBot/CCBot/bytespider.

Sampled 10 live articles from /rss.xml (2026-08-24): all were
`isAccessibleForFree: true` with full-text `<p>` content matching the
ld+json `wordCount` field (no truncation) -- the RSS feed appears to only
carry free articles, excluding "Aftonbladet Plus" premium pieces. The
extractor still checks `isAccessibleForFree` defensively for article-mode
URLs supplied directly by the user, which may include Plus content.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.aftonbladet.se"
WARMUP_URL = f"{BASE_URL}/"
RSS_URL = f"{BASE_URL}/rss.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
