"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-27): thestatesman.com (The Statesman, New Delhi --
national English-language Indian daily) sits behind **Cloudflare**, but a
plain `curl_cffi` `chrome124` impersonated request clears it cleanly on the
first try -- homepage, article pages, and both sitemaps all return a clean
200 with no `Just a moment...` interstitial. A *non*-impersonated
`requests` call to the same homepage gets a genuine Cloudflare JS-challenge
403 (`title: Just a moment...`), confirming the WAF is live and that TLS
impersonation alone (no cookie harvesting / challenge solving) is what
clears it here.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thestatesman.com"
WARMUP_URL = f"{BASE_URL}/"

# /feed and /rss both return a WordPress `wp_die` 500 ("No feed available")
# -- no RSS is exposed on this site. `latest` mode instead uses the Google
# News sitemap (referenced from robots.txt), confirmed live with 342
# <url> entries, each carrying <news:title> and <news:publication_date> --
# a purpose-built "most recent" feed, no extra parsing needed.
GOOGLENEWS_SITEMAP_URL = f"{BASE_URL}/googlenews.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
