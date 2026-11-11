"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): omanobserver.om (Oman Observer, Oman's
English-language national newspaper) has NO active WAF challenge -- it
sits behind Sucuri/Cloudproxy (`server: Sucuri/Cloudproxy`, `x-sucuri-id`
header present) but that header shows up on a clean chrome124 200, not a
challenge page. robots.txt has a single flat `User-agent: *` group (no
per-bot groups at all, so the documented Babak-14 multi-group-parser
trap does not apply here) with no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai disallow of any kind.
chrome124 gets a clean 200 on the homepage, article pages, and a
synthetic out-of-range article ID (real HTTP 404, not soft-404). See
CRAWLING_METHOD.md.

Both `/feed` (404) and every `sitemap*.xml` / `rss.xml` variant probed
(404) are absent. `/rss` itself returns HTTP 200 but is NOT a feed -- the
CMS renders its generic page template for any unmatched route with a
200 status (`class="OtherPage"`, empty content body) instead of a real
404, so `/rss` is a dead end, not a working feed. "latest" mode instead
scrapes the homepage for `/article/<id>/...` links (see extractor.py) --
the same homepage-fallback pattern used by chinadaily-scraper and
jamaicagleaner-scraper when RSS/sitemap discovery is broken.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.omanobserver.om"
WARMUP_URL = f"{BASE_URL}/"

# No working RSS/sitemap feed exists (see module docstring) -- the
# homepage doubles as the "latest" mode source, same as chinadaily-scraper.
LATEST_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
