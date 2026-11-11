"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): tribune.com.pk (The Express Tribune, Pakistan)
has NO active WAF challenge on real content -- chrome124 gets a clean 200
on the homepage, real article pages, and the latest-articles sitemap.

IMPORTANT quirk: Cloudflare runs a TARGETED anti-enumeration rule scoped
specifically to the `/story/<id>/...` URL pattern -- any `/story/` URL
whose numeric ID does not correspond to a real article returns an
immediate 403 "Just a moment..." challenge page, even though the exact
same TLS profile gets a clean 200 on real `/story/` URLs seconds before
and after. Non-`/story/`-shaped nonexistent paths (e.g. a random slug at
the site root) do NOT trigger this -- they soft-404 by rendering the
homepage shell (HTTP 200). This means a genuinely deleted/nonexistent
article ID is indistinguishable, from the client's perspective, from a
Cloudflare block: both this actor's `client.py` and `main.py` treat that
case as `_error: "blocked_or_transient"` (after exhausting retries) rather
than a clean `not_found`, since there is no way to tell the two apart
without a captcha-solve, which is out of scope. See CRAWLING_METHOD.md.

`/feed` returns 403 (WAF-blocked, unrelated to the article-ID rule above);
`/rss`, `/rss.xml`, `/feeds/rss` all return HTTP 200 but are NOT real
feeds -- they render the homepage/HTML shell, not XML. `robots.txt`
advertises `Sitemap: https://tribune.com.pk/sitemap/latest-1.xml`, a
real, clean, frequently-updated XML sitemap of recent articles -- used for
`latest` mode instead.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://tribune.com.pk"
WARMUP_URL = f"{BASE_URL}/"

LATEST_SITEMAP_URL = f"{BASE_URL}/sitemap/latest-1.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
