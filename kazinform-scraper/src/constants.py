"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): Kazinform is Kazakhstan's state news agency.
The Kazakh-language flagship domain `inform.kz` (aka `www.inform.kz`) only
carries Russian/Kazakh sitemaps in its robots.txt. The English edition
lives on a **separate domain**, `qazinform.com` — confirmed by following
`https://www.inform.kz/en/` -> 301 -> `https://en.inform.kz` -> 301 ->
`https://qazinform.com`. This actor is scoped entirely to `qazinform.com`
(English edition), the same pattern as `asharqalawsat-scraper` scoping to
the English subdomain of Asharq Al-Awsat.

No active WAF challenge was found on qazinform.com during recon: plain
`curl` (no TLS impersonation) and `curl_cffi` `chrome124`/`chrome131` all
get a clean 200 with identical byte size on the homepage and article
pages, served directly by nginx (no Cloudflare/challenge markers). Retry/
backoff scaffolding is kept anyway per portfolio convention. See
CRAWLING_METHOD.md for full recon notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://qazinform.com"
WARMUP_URL = f"{BASE_URL}/"

# ROR-format sitemap/feed -- newest-first, `content:encoded` carries the
# full article body HTML (see CRAWLING_METHOD.md).
LATEST_FEED_URL = f"{BASE_URL}/feed.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
