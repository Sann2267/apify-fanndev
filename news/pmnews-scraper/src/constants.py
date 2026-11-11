"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): pmnewsnigeria.com (P.M. News, Lagos-based Nigerian
tabloid) sits behind Cloudflare (`server: cloudflare`, `cf-ray` present) but
shows NO active JA3/TLS-fingerprint challenge for normal traffic --
`curl_cffi` `chrome124` gets a clean 200 on the homepage, article pages,
`/feed/`, `/sitemap_index.xml`, and the WP REST API. robots.txt is a stock
Yoast SEO block (`User-agent: *` / `Disallow:` empty -- allow-all, plus a
`/?s=*`/`/search/` search-path disallow this actor never touches) with no
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
disallow of any kind, and no natural-language AI/scraping prohibition
anywhere in the file.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk on this site. The WP REST
API (`?slug=<bad-slug>`) independently confirms this, returning HTTP 200
with an empty JSON array `[]` for the same invented slug.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://pmnewsnigeria.com"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
