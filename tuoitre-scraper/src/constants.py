"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): tuoitrenews.vn (Tuoi Tre News, Vietnam's
largest-circulation newspaper, English edition) has NO active WAF
challenge. robots.txt is a single trivial group (`User-agent: *`
`Allow: /`), no Claude/GPTBot/anthropic-ai disallow of any kind. chrome124
gets a clean 200 on homepage, article pages, and the RSS feed.

IMPORTANT quirk: tuoitrenews.vn transparently 302-redirects EVERY request
(homepage, articles, /rss) to news.tuoitre.vn -- a dedicated English-
edition subdomain of tuoitre.vn (NOT the Vietnamese-language main site,
which was never screened). news.tuoitre.vn's own robots.txt was verified
separately and is equally permissive (`Allow: /`). Since curl_cffi follows
redirects by default, feeding it tuoitrenews.vn URLs "just works" -- the
client naturally lands on news.tuoitre.vn. See CRAWLING_METHOD.md.

Real 404s confirmed (synthetic out-of-range article slug returns a real
HTTP 404 with a Vietnamese "Trang thông báo lỗi 404" error page).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://tuoitrenews.vn"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
