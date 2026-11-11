"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-27): scroll.in sits behind Cloudflare (`server:
cloudflare` header present) but no bot-fight-mode / JS-challenge was
observed -- a plain `urllib.request` GET (no TLS impersonation at all) got a
clean 200 on the homepage, and `curl_cffi` `chrome124` got clean 200s on
homepage, article pages (all 4 content-type prefixes: article/magazine/reel/
latest), the news sitemap, and the Feedburner RSS mirror. No cf-ray
challenge body, no captcha-delivery/datadome/_abck markers anywhere.
`chrome124` is pinned anyway per the portfolio-wide default of avoiding the
most-blocklisted `chrome131` profile even when it currently works.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://scroll.in"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, referenced from robots.txt (`Sitemap:` directive).
# Confirmed live 2026-08-27: 100+ <url> entries, each carrying `news:title`
# and a real per-article `news:publication_date` (IST offset), already
# newest-first in file order. Used instead of the site's own `/feed` path
# (which does NOT return RSS -- it 200s with the homepage HTML shell
# instead, a dead end) and instead of the third-party Feedburner mirror
# (`https://feeds.feedburner.com/ScrollinArticles.rss`, also confirmed
# live) to keep `latest` mode entirely on-domain, matching the
# guardian-nigeria-scraper precedent.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
