"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-27): tribuneindia.com (The Tribune, Chandigarh --
major North India English daily) has NO WAF in front of it. `curl_cffi`
`chrome124` returns a clean 200 on the homepage, article pages, and both
sitemaps on the first try -- `server: nginx`, no `cf-ray`/`x-datadome`/
`_abck`/Fastly markers, no challenge body.

`/feed`, `/feed/`, `/rss.xml`, `/rssfeed.xml`, `/news/rss.xml` all return a
plain 403/404 (no RSS is exposed) -- `latest` mode uses `/recent-sitemap.xml`
instead (referenced from robots.txt), which is unaffected and was confirmed
live with 100 real, current article entries.

robots.txt (`https://www.tribuneindia.com/robots.txt`) is a minimal 4-line
file: `User-agent: *` / `Allow: /` plus three `Sitemap:` lines. No Disallow
directives at all, no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai block of any kind, and no natural-language
prohibition in comments -- fully crawlable.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.tribuneindia.com"
WARMUP_URL = f"{BASE_URL}/"

# /feed and /feed/ return 403, no other RSS path found -- this sitemap
# (referenced from robots.txt) is the latest-mode source instead. Confirmed
# live: exactly 100 entries, each carrying <loc>, <lastmod>, and
# <image:image><image:title> (used as the headline text). Not guaranteed
# strictly newest-first in file order (spot-checked out of strict order
# across adjacent entries) -- extract_sitemap_items() sorts descending by
# lastmod defensively.
RECENT_SITEMAP_URL = f"{BASE_URL}/recent-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
