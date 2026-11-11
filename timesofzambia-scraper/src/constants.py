"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): times.co.zm (Times of Zambia, state-owned daily,
Zambia's oldest newspaper) shows NO active WAF challenge. `curl_cffi`
`chrome124` gets a clean 200 -- with zero cookies set -- on the homepage,
article pages, the WordPress REST API, and the RSS feed. The full profile
ladder (chrome124/chrome99_android/safari17_0/edge101/firefox133) was run
against the homepage and every profile returned an identical 200/140534
bytes, confirming there is no JA3-specific gate either. robots.txt has a
SINGLE `User-agent: *` group (`Disallow: /wp-admin/`, `Allow:
/wp-admin/admin-ajax.php`) -- so there is no possibility of the Babak-14
merged-Disallow-block parser bug here (that bug only bites when several
`User-agent` groups share one `Disallow` block; this site has exactly one
group). No Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai token appears anywhere in the file. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://times.co.zm"
WARMUP_URL = f"{BASE_URL}/"

# WordPress REST API -- primary article data source (S1-wpapi). Public,
# unauthenticated, not disallowed by robots.txt. `_embed=1` inlines the
# author (real name, not just a numeric ID), featured-media object, and
# category/tag term objects in one round trip.
WP_API_POSTS_URL = f"{BASE_URL}/wp-json/wp/v2/posts"

# RSS feed -- latest mode (S2-rss). Default WordPress feed, 10 items per
# page, paginates via `?paged=N`.
RSS_FEED_URL = f"{BASE_URL}/feed/"
RSS_ITEMS_PER_PAGE = 10

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
