"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): leadership.ng (LEADERSHIP Newspapers, Nigerian
national daily -- "For God and Country") sits behind Cloudflare (`server:
cloudflare`, `cf-ray` present) but shows NO active JA3/TLS-fingerprint
challenge for normal traffic -- plain `requests`/`curl` already gets a clean
200 on the homepage, article pages, and `/feed/`; `curl_cffi` `chrome124`
confirms the same. No stale-edge-cache quirk observed (unlike
premiumtimesng.com) on the samples checked.

robots.txt is a minimal custom block (not the usual stock Yoast one seen on
other Nigerian WordPress outlets in this portfolio):

    User-agent: *
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php
    Sitemap: https://leadership.ng/sitemap_index.xml

Allow-all for everything except /wp-admin/ -- no Claude/ClaudeBot/
Claude-Web/Claude-SearchBot/anthropic-ai disallow of any kind, and only one
user-agent group.

Deleted/never-existed article slugs 200-OK to the **homepage** instead of a
real 404 (soft-404, same pattern as premiumtimesng.com) -- confirmed on a
deliberately-invented slug (final response is the literal homepage HTML,
same title, no `Article` node in the ld+json graph). See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://leadership.ng"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feed/"
RSS_PAGE_SIZE = 10

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
