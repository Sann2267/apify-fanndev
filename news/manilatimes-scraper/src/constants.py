"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): manilatimes.net has NO active WAF challenge
(Cloudflare CDN present but never issues a JS challenge for chrome124).
robots.txt (206 bytes, User-agent: * only) has no Claude/GPTBot/anthropic-ai
disallow -- just /ajax/*, /*.pdf, /widget/*, */page/*, /search* and a
Crawl-delay: 600 (10 minutes; not enforced by this actor beyond the normal
retry/backoff, per portfolio convention of not auto-throttling to spec-only
crawl-delay values, but noted for anyone tuning maxConcurrency).
chrome124 gets a clean 200 on homepage, article pages, and the site-wide
"Latest News" RSS feed. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.manilatimes.net"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "Latest News" feed spanning every section (News, Business, Sports,
# World, Entertainment & Lifestyle, TMT Newswire, ...). Confirmed live, 50
# items per fetch. (Category-scoped feeds also exist, e.g. /news/feed/, but
# this one is the broadest "latest" source.)
RSS_URL = f"{BASE_URL}/latest/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-PH,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
