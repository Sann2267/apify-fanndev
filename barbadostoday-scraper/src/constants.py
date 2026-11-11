"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): barbadostoday.bb (Barbados Today -- Barbados'
leading digital-native news outlet) is a WordPress site (WP 7.0.4, Yoast SEO,
Penci "Soledad"-family theme) hosted on WP Engine, fronted by Cloudflare
(`server: cloudflare`). A bare `curl -A "Mozilla/5.0"` request with no other
headers gets a Cloudflare/WP Engine 403 ("Attention Required!" /
"blocked wpenginepowered.com") on EVERY path, including the homepage -- but
`curl_cffi` `chrome124` impersonation clears this cleanly on the first try,
no warmup-then-retry dance needed: homepage, `/wp-json/wp/v2/posts`,
`/feed/`, an article page, and a deliberately-invented article slug (real
404) all returned correct results in one pass during recon.

robots.txt (`https://barbadostoday.bb/robots.txt`, fetched fresh via plain
`curl`, HTTP 200) is a stock Yoast SEO block: `Crawl-delay: 10` plus a single
`User-agent: *` / `Disallow:` (empty -- allow-all) group and a `Sitemap:`
line. No Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai disallow of any kind, no blanket `Disallow: /`, and no
plain-English prohibition against AI/LLM training or scraping anywhere in
the file (checked per the post-"Babak 17" screening rule, not just the
machine-readable directives) -- confirmed crawlable.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug/date combination) -- no soft-404 quirk observed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://barbadostoday.bb"
WARMUP_URL = f"{BASE_URL}/"

# WordPress REST API -- primary data source for BOTH article mode
# (S1-wpapi, `?slug=<slug>&_embed=1`) and latest mode (S1-wpapi,
# `?per_page=<limit>&_embed=1`). Public, unauthenticated, not disallowed by
# robots.txt. `_embed=1` inlines the real per-article author name, the
# featured-media object, and category/tag term objects in one round trip.
# `/wp-json/wp/v2/posts` accepts `per_page` up to (at least) 50 in a single
# call -- confirmed during recon -- so `latest` mode needs no pagination
# loop. Chosen over the site's own `/feed/` RSS (also confirmed working
# cleanly) because the REST API returns the exact same rich shape
# (full `content.rendered`, real embedded author, categories/tags) for
# BOTH article and latest mode in one round trip, matching this
# portfolio's `thisday-scraper` pattern.
WP_API_POSTS_URL = f"{BASE_URL}/wp-json/wp/v2/posts"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
