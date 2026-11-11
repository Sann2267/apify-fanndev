"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): postcourier.com.pg (Post Courier, Papua New
Guinea's leading daily newspaper since 1969) shows NO active WAF challenge.
A plain `requests`/`curl` baseline (no TLS impersonation) already gets clean
HTTP 200 on `/robots.txt`, the homepage, article pages, `/wp-json/wp/v2/...`,
`/feed/`, and `/news-sitemap.xml`. `curl_cffi` `chrome124` is still used as
the portfolio-wide default TLS profile for consistency and future-proofing,
not because it was required to clear a block.

robots.txt carries a stock Yoast SEO block (`User-agent: *` / `Disallow:`
empty -- allow-all) plus a small WooCommerce-asset disallow list
(`/wp-content/uploads/wc-logs/`, `/wp-admin/`, `?add-to-cart=`) -- all
routine WordPress/WooCommerce system paths, not anti-scraping rules. No
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
disallow directive anywhere, and no plain-English prohibition against
AI/LLM training or scraping in any comment. Two `Sitemap:` lines point at
`sitemap.xml` / `news-sitemap.xml` (top block) and `sitemap_index.xml`
(Yoast block).

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed.

**Hard paywall (WooCommerce Memberships):** most PNG-local news (categories
like "PNG News", "Business", "Sports") is gated -- the WordPress REST API
`content.rendered` for a paywalled post contains only a ~2-paragraph
`div.content-preview` teaser followed by a
`div.wc-memberships-restriction-message` upsell block, never the full body.
Wire-service / regional stories (mostly tagged "World" / "World News" --
PACNEWS Pacific-region content) are frequently free with full text. Roughly
17% of a ~80-post recent sample were free in this recon pass. See
CRAWLING_METHOD.md for the detection logic.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.postcourier.com.pg"
WARMUP_URL = f"{BASE_URL}/"

# RSS feed -- confirmed live (HTTP 200, populated with recent items) during
# recon, unlike some smaller regional-daily actors in this portfolio where
# RSS/sitemap is broken and a homepage-link-scrape fallback is required.
LATEST_FEED_URL = f"{BASE_URL}/feed/"

# WordPress REST API -- used per-article (by slug) to fetch the structured
# content.rendered body plus embedded author/media/term data in one request.
WP_API_POSTS_URL = f"{BASE_URL}/wp-json/wp/v2/posts"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
