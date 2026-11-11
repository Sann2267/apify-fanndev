"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): thisdaylive.com (THISDAYLIVE, Nigerian national
daily) shows NO active WAF challenge. `curl_cffi` `chrome124` gets a clean
200 on the homepage, article pages, and the WordPress REST API -- and even
plain `curl` (no TLS impersonation at all) gets clean 200s on the homepage,
the REST API, and a real 404 on a deliberately-invented article slug.
robots.txt (`https://www.thisdaylive.com/robots.txt`, fetched fresh, HTTP
200) has a `User-agent: *` block disallowing only `/wp-admin/`,
`/wp-includes/`, `/wp-content/plugins/`, `/wp-content/themes/`, `/private/`,
`/secret-page/`, `/page/`, `*/page/`, `/*?amp=1`, `/wp-login.php`,
`/wp-register.php`, plus separate full-site `Disallow: /` blocks for
Bytespider/SemrushBot/PetalBot/Amazonbot/Bingbot/DotBot/Baiduspider. No
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai token
appears anywhere in the file, and `/wp-json/` is not disallowed for the
default `User-agent: *` group this actor's UA falls under. See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thisdaylive.com"
WARMUP_URL = f"{BASE_URL}/"

# WordPress REST API -- primary data source for BOTH article mode
# (S1-wpapi, `?slug=<slug>&_embed=1`) and latest mode (S1-wpapi,
# `?per_page=<limit>&_embed=1`). Public, unauthenticated, not disallowed by
# robots.txt. `_embed=1` inlines the real per-article author name, the
# featured-media object, and category/tag term objects in one round trip.
# `/wp-json/wp/v2/posts` accepts `per_page` up to (at least) 50 in a single
# call -- confirmed during recon -- so `latest` mode needs no pagination
# loop, unlike some other actors in this portfolio.
WP_API_POSTS_URL = f"{BASE_URL}/wp-json/wp/v2/posts"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
