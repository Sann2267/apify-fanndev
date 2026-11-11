"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): nationthailand.com (The Nation Thailand,
English-language business/general daily) has NO active WAF challenge.
robots.txt is a simple `User-agent: * / Disallow: /search, /*.php,
/*.htm*` group, no Claude/GPTBot/anthropic-ai disallow of any kind, and
advertises `Sitemap: https://www.nationthailand.com/sitemap/latest` (used
for "latest" mode) plus a full site index and a tag sitemap. chrome124
gets a clean 200 on the homepage, article pages, and the sitemap.

Soft-404 quirk: a nonexistent article ID returns HTTP 200 rendering the
homepage shell (identical byte length to a real homepage fetch), not a
distinct error page. Detected instead via `<link rel="canonical">`: on a
real article it matches the requested URL; on a soft-404 it points to
`https://www.nationthailand.com/` instead. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.nationthailand.com"
WARMUP_URL = f"{BASE_URL}/"

LATEST_SITEMAP_URL = f"{BASE_URL}/sitemap/latest"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
