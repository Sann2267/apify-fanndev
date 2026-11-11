"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): jamaica-gleaner.com (The Gleaner, Jamaica's
oldest and largest newspaper) has NO active WAF challenge. robots.txt is
a standard Drupal-generated file (disallows only `/admin/`, `/core/`,
`/profiles/`, `/user/register`, `/search/`, etc. -- CMS system paths, no
Claude/GPTBot/anthropic-ai disallow of any kind). chrome124 gets a clean
200 on the homepage and article pages. Real 404s confirmed (synthetic
out-of-range article slug).

Both discovery mechanisms this project would normally reach for first are
confirmed broken on this site (matches prior recon-session notes -- this
is not new): `sitemap.xml` returns 404, and `rss.xml` returns HTTP 200
but is a genuinely empty stub (`<channel>` with zero `<item>` elements).
`latest` mode instead scrapes the homepage for `/article/<section>/
<YYYYMMDD>/<slug>` links -- the date is embedded directly in the URL path,
so results are sortable newest-first without visiting each article page
first, the same strategy already used by chinadaily-scraper /
globaltimes-scraper when a site's official feed/sitemap is unusable.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://jamaica-gleaner.com"
WARMUP_URL = f"{BASE_URL}/"
LATEST_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
