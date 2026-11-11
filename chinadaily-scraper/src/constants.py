"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): chinadaily.com.cn (China Daily, China's
official English-language state newspaper) has NO active WAF challenge.
robots.txt is a real HTTP 404 (not just an empty file -- confirmed by
body: it serves the site's generic 404 page, same shape as a missing
article page). chrome124 gets a clean 200 on the homepage, article
pages, section listing pages, and a synthetic-404 test URL.

Both `/rss/china_rss.xml` and `/sitemap.xml` return HTTP 200 but are
**dead/frozen artifacts** -- the RSS feed's newest item is dated
December 2017 and the sitemap's newest `lastmod` is from 2014. Neither
is usable for "latest" mode. The homepage (`BASE_URL`) is used instead:
it lists ~100+ recent article links across all sections, and the
article ID embedded in each URL (`/a/YYYYMM/DD/WS<hex>.html`) sorts
lexically = chronologically, so no per-article fetch is needed to order
results. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.chinadaily.com.cn"
WARMUP_URL = f"{BASE_URL}/"

# Homepage doubles as the "latest" mode source -- RSS and sitemap.xml
# are both stale/dead (see module docstring above).
LATEST_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
